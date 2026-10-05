"""Cross-league matchups. Totals use the provider's reported team points (authoritative);
player rows use our engine, and gaps > GAP_THRESHOLD are logged to catch stat-map bugs."""

from pydantic import BaseModel
from sqlmodel import Session

from app.domain.models import FantasyMatchup, FantasyTeam, User
from app.errors import NotFound
from app.game_day.contexts import (
    RosterContext,
    build_rows,
    collect_contexts,
    league_matchup,
    manual_teams,
    profile_rules,
    refresh_leagues,
    roster_entries,
    week_snapshot,
)
from app.game_day.grouping import row_sort_key
from app.game_day.schemas import LeagueError, PlayerRow
from app.game_day.service import is_game_day, resolve_week, week_games
from app.logging import log
from app.nfl_data.sync import ensure_week_fresh
from app.providers.sync import get_user_league

GAP_THRESHOLD = 0.5


class MatchupSide(BaseModel):
    team_id: int | None
    name: str
    owner_name: str | None = None
    score: float | None
    projected: float | None = None


class MatchupCard(BaseModel):
    id: int | None
    league_id: int | None
    league_name: str
    provider: str
    week: int
    status: str | None
    has_matchup: bool
    my_team: MatchupSide
    opponent: MatchupSide | None


class MatchupsResponse(BaseModel):
    season: int
    week: int
    matchups: list[MatchupCard]
    league_errors: list[LeagueError]


class MatchupDetail(BaseModel):
    card: MatchupCard
    my_starters: list[PlayerRow]
    opponent_starters: list[PlayerRow]
    my_engine_total: float
    opponent_engine_total: float


def _engine_total(rows: list[PlayerRow]) -> float:
    return round(sum(r.points or 0 for r in rows), 2)


def _card(db: Session, m: FantasyMatchup, league_name: str, provider: str) -> MatchupCard:
    mine = db.get(FantasyTeam, m.user_team_id)
    opp = db.get(FantasyTeam, m.opponent_team_id) if m.opponent_team_id else None
    return MatchupCard(
        id=m.id,
        league_id=m.league_id,
        league_name=league_name,
        provider=provider,
        week=m.week,
        status=m.status,
        has_matchup=True,
        my_team=MatchupSide(
            team_id=m.user_team_id,
            name=mine.name if mine else "My team",
            owner_name=mine.owner_name if mine else None,
            score=m.user_score,
            projected=m.user_projected,
        ),
        opponent=MatchupSide(
            team_id=m.opponent_team_id,
            name=opp.name if opp else "Opponent",
            owner_name=opp.owner_name if opp else None,
            score=m.opponent_score,
            projected=m.opponent_projected,
        )
        if m.opponent_team_id
        else None,
    )


def list_matchups(
    db: Session, user: User, season: int | None = None, week: int | None = None, *, force: bool = False
) -> MatchupsResponse:
    season, week = resolve_week(db, season, week)
    ensure_week_fresh(db, season, week)
    games = week_games(db, season, week)
    leagues, errors = refresh_leagues(db, user, week, game_day=is_game_day(games), force=force)
    cards: list[MatchupCard] = []
    for league in leagues:
        if league.selected_team_id is None:
            continue
        m = league_matchup(db, league, week)
        if m is not None:
            cards.append(_card(db, m, league.name, league.provider))

    # Custom teams have no opponent; show their engine total so they still read as a scoreboard.
    contexts = collect_contexts(db, user, [], season, week)
    rows = build_rows(db, contexts, season, week, games)
    for team in manual_teams(db, user):
        starters = [r for r in rows if r.team_id == team.id and r.ownership == "MY_STARTER"]
        cards.append(
            MatchupCard(
                id=None,
                league_id=None,
                league_name=team.name,
                provider="manual",
                week=week,
                status=None,
                has_matchup=False,
                my_team=MatchupSide(team_id=team.id, name=team.name, score=_engine_total(starters)),
                opponent=None,
            )
        )
    return MatchupsResponse(season=season, week=week, matchups=cards, league_errors=errors)


def matchup_detail(db: Session, user: User, matchup_id: int) -> MatchupDetail:
    m = db.get(FantasyMatchup, matchup_id)
    if m is None:
        raise NotFound("That matchup doesn't exist.")
    league = get_user_league(db, user, m.league_id)  # enforces ownership
    games = week_games(db, m.season, m.week)
    rules = profile_rules(db, league.scoring_profile_id)

    def ctx(team_id: int | None, is_user_team: bool) -> list[RosterContext]:
        team = db.get(FantasyTeam, team_id) if team_id else None
        if team is None or team.id is None:
            return []
        snap = week_snapshot(db, team.id, m.season, m.week)
        return [
            RosterContext(league.id, league.name, league.provider, team, is_user_team, rules, roster_entries(db, snap))
        ]

    mine = [
        r for r in build_rows(db, ctx(m.user_team_id, True), m.season, m.week, games) if r.ownership == "MY_STARTER"
    ]
    # Opponent rows classify as OPPONENT (starters only).
    theirs = build_rows(db, ctx(m.opponent_team_id, False), m.season, m.week, games)
    mine.sort(key=row_sort_key)
    theirs.sort(key=row_sort_key)

    my_total, opp_total = _engine_total(mine), _engine_total(theirs)
    for side, provider_total, engine_total in (
        ("me", m.user_score, my_total),
        ("opponent", m.opponent_score, opp_total),
    ):
        if provider_total is not None and abs(provider_total - engine_total) > GAP_THRESHOLD:
            log.debug(
                "matchup_score_gap",
                matchup_id=m.id,
                side=side,
                provider_total=provider_total,
                engine_total=engine_total,
            )
    return MatchupDetail(
        card=_card(db, m, league.name, league.provider),
        my_starters=mine,
        opponent_starters=theirs,
        my_engine_total=my_total,
        opponent_engine_total=opp_total,
    )
