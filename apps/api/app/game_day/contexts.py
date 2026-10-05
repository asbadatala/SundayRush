"""Roster contexts: one (league, fantasy team, scoring rules, roster) per thing the user
tracks. The same NFL player can appear in many contexts; each stays separate."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.domain.models import (
    CanonicalPlayer,
    FantasyLeague,
    FantasyMatchup,
    FantasyTeam,
    NFLGame,
    PlayerGameStats,
    RosterEntry,
    RosterSnapshot,
    ScoringProfile,
    User,
)
from app.errors import AppError, TeamNotSelected
from app.game_day.ownership import classify
from app.game_day.schemas import LeagueError, PlayerRow
from app.logging import log
from app.providers.manual.adapter import latest_snapshot
from app.providers.sync import list_user_leagues, sync_league
from app.scoring.engine import UNSCORED_POSITIONS, points_for_position


@dataclass
class RosterContext:
    league_id: int | None
    league_name: str
    provider: str
    team: FantasyTeam
    is_user_team: bool
    rules: dict[str, float]
    entries: list[RosterEntry]


def profile_rules(db: Session, profile_id: int | None) -> dict[str, float]:
    profile = db.get(ScoringProfile, profile_id) if profile_id else None
    return dict(profile.scoring_json) if profile else {}


def roster_entries(db: Session, snapshot: RosterSnapshot | None) -> list[RosterEntry]:
    if snapshot is None:
        return []
    return list(db.exec(select(RosterEntry).where(RosterEntry.roster_snapshot_id == snapshot.id)))


def week_snapshot(db: Session, team_id: int, season: int, week: int) -> RosterSnapshot | None:
    """Exact week, else the most recent earlier snapshot (stale but better than nothing)."""
    return db.exec(
        select(RosterSnapshot)
        .where(
            RosterSnapshot.fantasy_team_id == team_id,
            RosterSnapshot.season == season,
            col(RosterSnapshot.week) <= week,
        )
        .order_by(col(RosterSnapshot.week).desc())
    ).first()


def league_matchup(db: Session, league: FantasyLeague, week: int) -> FantasyMatchup | None:
    return db.exec(
        select(FantasyMatchup).where(
            FantasyMatchup.league_id == league.id,
            FantasyMatchup.season == league.season,
            FantasyMatchup.week == week,
            FantasyMatchup.user_team_id == league.selected_team_id,
        )
    ).first()


def manual_teams(db: Session, user: User) -> list[FantasyTeam]:
    return list(
        db.exec(
            select(FantasyTeam)
            .where(FantasyTeam.user_id == user.id, FantasyTeam.is_manual == True)  # noqa: E712
            .order_by(col(FantasyTeam.id))
        )
    )


def to_league_error(league: FantasyLeague, exc: AppError) -> LeagueError:
    return LeagueError(
        league_id=league.id, league_name=league.name, provider=league.provider, code=exc.code, message=exc.message
    )


def refresh_leagues(
    db: Session, user: User, week: int, *, game_day: bool, force: bool
) -> tuple[list[FantasyLeague], list[LeagueError]]:
    """Refresh each imported league if stale. Failures are reported inline, never raised."""
    errors: list[LeagueError] = []
    leagues = list_user_leagues(db, user)
    for league in leagues:
        try:
            if league.selected_team_id is None:
                raise TeamNotSelected(f"Pick your team in {league.name} to see it on game day.")
            sync_league(db, user, league, week, force=force, game_day=game_day)
        except AppError as exc:
            db.rollback()
            log.warning("league_refresh_failed", league_id=league.id, code=exc.code)
            errors.append(to_league_error(league, exc))
    return leagues, errors


def collect_contexts(
    db: Session, user: User, leagues: Sequence[FantasyLeague], season: int, week: int
) -> list[RosterContext]:
    contexts: list[RosterContext] = []
    for league in leagues:
        if league.selected_team_id is None:
            continue
        rules = profile_rules(db, league.scoring_profile_id)
        my_team = db.get(FantasyTeam, league.selected_team_id)
        if my_team is None or my_team.id is None:
            continue
        contexts.append(
            RosterContext(
                league.id,
                league.name,
                league.provider,
                my_team,
                True,
                rules,
                roster_entries(db, week_snapshot(db, my_team.id, league.season, week)),
            )
        )
        matchup = league_matchup(db, league, week)
        if matchup and matchup.opponent_team_id:
            opp = db.get(FantasyTeam, matchup.opponent_team_id)
            if opp is not None and opp.id is not None:
                contexts.append(
                    RosterContext(
                        league.id,
                        league.name,
                        league.provider,
                        opp,
                        False,
                        rules,
                        roster_entries(db, week_snapshot(db, opp.id, league.season, week)),
                    )
                )
    for team in manual_teams(db, user):
        assert team.id is not None
        contexts.append(
            RosterContext(
                None,
                team.name,
                "manual",
                team,
                True,
                profile_rules(db, team.scoring_profile_id),
                roster_entries(db, latest_snapshot(db, team.id)),
            )
        )
    return contexts


_STAT_PARTS: list[tuple[str, str]] = [
    ("pass_yards", "PASS YDS"),
    ("pass_td", "PASS TD"),
    ("interception", "INT"),
    ("rush_yards", "RUSH YDS"),
    ("rush_td", "RUSH TD"),
    ("reception", "REC"),
    ("receiving_yards", "REC YDS"),
    ("receiving_td", "REC TD"),
    ("return_td", "RET TD"),
    ("fumble_lost", "FUM LOST"),
    ("fg_made", "FG"),
    ("xp_made", "XP"),
    ("def_sack", "SACK"),
    ("def_interception", "INT"),
    ("def_td", "TD"),
    ("def_points_allowed", "PA"),
]


def format_stat_line(stats: dict[str, float] | None) -> str | None:
    if not stats:
        return None
    parts = []
    if stats.get("pass_att"):
        parts.append(f"{int(stats.get('pass_cmp', 0))}/{int(stats['pass_att'])}")
    for key, label in _STAT_PARTS:
        value = stats.get(key)
        if value:
            parts.append(f"{value:g} {label}")
    return ", ".join(parts) or None


def build_rows(
    db: Session, contexts: list[RosterContext], season: int, week: int, games: list[NFLGame]
) -> list[PlayerRow]:
    player_ids = {e.player_id for c in contexts for e in c.entries if e.player_id is not None}
    players = (
        {p.id: p for p in db.exec(select(CanonicalPlayer).where(col(CanonicalPlayer.id).in_(player_ids)))}
        if player_ids
        else {}
    )
    stats = (
        {
            s.player_id: s
            for s in db.exec(
                select(PlayerGameStats).where(
                    col(PlayerGameStats.player_id).in_(player_ids),
                    PlayerGameStats.season == season,
                    PlayerGameStats.week == week,
                )
            )
        }
        if player_ids
        else {}
    )
    game_by_team: dict[str, NFLGame] = {}
    for g in games:
        game_by_team[g.home_team] = g
        game_by_team[g.away_team] = g

    rows: list[PlayerRow] = []
    for ctx in contexts:
        assert ctx.team.id is not None
        for e in ctx.entries:
            ownership = classify(is_user_team=ctx.is_user_team, is_starter=e.is_starter)
            if ownership is None:
                continue
            player = players.get(e.player_id) if e.player_id is not None else None
            key = f"{ctx.team.id}:{e.player_id or 'x' + str(e.provider_player_id)}"
            if player is None:
                rows.append(
                    PlayerRow(
                        key=key,
                        player_id=None,
                        name=e.provider_player_name or "Unknown player",
                        position=(e.provider_position or "?").upper(),
                        nfl_team=e.provider_nfl_team.upper() if e.provider_nfl_team else None,
                        league_id=ctx.league_id,
                        league_name=ctx.league_name,
                        team_id=ctx.team.id,
                        team_name=ctx.team.name,
                        provider=ctx.provider,
                        ownership=ownership,
                        slot=e.slot,
                        points=None,
                        points_unavailable_reason="Player couldn't be matched to an NFL player",
                        injury_status=e.provider_status,
                        mapped=False,
                    )
                )
                continue
            game = game_by_team.get(player.nfl_team_code or "")
            stat = stats.get(player.id) if player.id is not None else None
            raw = stat.raw_stats_json if stat else None
            points = points_for_position(player.position, raw, ctx.rules)
            reason = None
            if player.position in UNSCORED_POSITIONS:
                reason = f"{player.position} scoring isn't supported yet"
            rows.append(
                PlayerRow(
                    key=key,
                    player_id=player.id,
                    name=player.full_name,
                    position=player.position,
                    nfl_team=player.nfl_team_code,
                    league_id=ctx.league_id,
                    league_name=ctx.league_name,
                    team_id=ctx.team.id,
                    team_name=ctx.team.name,
                    provider=ctx.provider,
                    ownership=ownership,
                    slot=e.slot,
                    points=points,
                    points_unavailable_reason=reason,
                    injury_status=e.provider_status or player.injury_status,
                    stat_line=format_stat_line(raw),
                    game_id=game.id if game else None,
                    game_status=game.status if game else None,
                )
            )
    return rows
