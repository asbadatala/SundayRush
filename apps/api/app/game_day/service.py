"""GET /api/game-day: one pre-grouped response for the primary screen (spec §10.6, §16)."""

import time
from datetime import timedelta

from sqlmodel import Session, select

from app.domain.models import NFLGame, User, utcnow
from app.domain.normalized import LIVE_STATUSES, GameStatus
from app.game_day.contexts import build_rows, collect_contexts, manual_teams, refresh_leagues
from app.game_day.grouping import group_rows
from app.game_day.schemas import GameDayResponse, GameOut, LeagueError
from app.logging import log
from app.nfl_data.sync import ensure_week_fresh, get_current_state


def week_games(db: Session, season: int, week: int) -> list[NFLGame]:
    return list(db.exec(select(NFLGame).where(NFLGame.season == season, NFLGame.week == week)))


def is_game_day(games: list[NFLGame]) -> bool:
    now = utcnow()
    return any(GameStatus(g.status) in LIVE_STATUSES or abs(g.kickoff_at - now) < timedelta(hours=12) for g in games)


def game_out(g: NFLGame) -> GameOut:
    assert g.id is not None
    return GameOut(
        id=g.id,
        external_game_id=g.external_game_id,
        kickoff_at=g.kickoff_at,
        home_team=g.home_team,
        away_team=g.away_team,
        home_score=g.home_score,
        away_score=g.away_score,
        status=g.status,
        status_detail=g.status_detail,
        quarter=g.quarter,
        clock=g.clock,
        broadcaster=g.broadcaster,
    )


def resolve_week(db: Session, season: int | None, week: int | None) -> tuple[int, int]:
    if season is not None and week is not None:
        return season, week
    state = get_current_state(db)
    return season or state.season, week or state.week


def build_game_day(
    db: Session, user: User, season: int | None = None, week: int | None = None, *, force: bool = False
) -> GameDayResponse:
    start = time.perf_counter()
    season, week = resolve_week(db, season, week)

    nfl = ensure_week_fresh(db, season, week, force=force)
    games = week_games(db, season, week)
    errors: list[LeagueError] = []
    if nfl.error is not None:
        errors.append(
            LeagueError(
                league_id=None, league_name="NFL data", provider="nfl", code=nfl.error.code, message=nfl.error.message
            )
        )

    leagues, league_errors = refresh_leagues(db, user, week, game_day=is_game_day(games), force=force)
    errors.extend(league_errors)
    contexts = collect_contexts(db, user, leagues, season, week)
    rows = build_rows(db, contexts, season, week, games)
    groups, no_game = group_rows(rows, [game_out(g) for g in games])

    team_count = sum(1 for lg in leagues if lg.selected_team_id) + len(manual_teams(db, user))
    response = GameDayResponse(
        season=season,
        week=week,
        generated_at=utcnow(),
        stats_as_of=nfl.stats_as_of,
        live_data_available=nfl.error is None,
        any_live=any(GameStatus(g.status) in LIVE_STATUSES for g in games),
        has_teams=bool(leagues) or team_count > 0,
        team_count=team_count,
        games=groups,
        no_game=no_game,
        league_errors=errors,
    )
    log.info(
        "game_day_built",
        season=season,
        week=week,
        contexts=len(contexts),
        rows=len(rows),
        errors=len(errors),
        latency_ms=round((time.perf_counter() - start) * 1000, 1),
    )
    return response
