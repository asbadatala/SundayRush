"""Persist NFL data from the NFLDataProvider into canonical tables, with staleness checks.

CLI: `uv run python -m app.nfl_data.sync_players`
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.cache.base import Cache
from app.cache.db_cache import DbCache
from app.domain.models import CanonicalPlayer, NFLGame, PlayerGameStats, utcnow
from app.domain.normalized import LIVE_STATUSES, GameStatus, NFLState, NormalizedNFLGame
from app.errors import AppError
from app.logging import log
from app.nfl_data.base import NFLDataProvider
from app.nfl_data.composite import get_nfl_data_provider
from app.player_resolution.names import normalize_name

PLAYERS_TTL = 24 * 3600
STATE_TTL = 3600
LIVE_TTL = 60
IDLE_TTL = 3600


def sync_players(session: Session, provider: NFLDataProvider | None = None) -> int:
    provider = provider or get_nfl_data_provider()
    start = time.perf_counter()
    players = provider.get_players()
    now = utcnow()
    rows = [
        {
            "sleeper_id": p.sleeper_id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "full_name": p.full_name,
            "normalized_name": normalize_name(p.full_name),
            "position": p.position,
            "nfl_team_code": p.nfl_team,
            "active_status": p.active_status,
            "injury_status": p.injury_status,
            "gsis_id": p.gsis_id,
            "espn_id": p.espn_id,
            "yahoo_id": p.yahoo_id,
            "stats_provider_id": p.stats_provider_id,
            "search_rank": p.search_rank,
            "updated_at": now,
        }
        for p in players
    ]
    for i in range(0, len(rows), 1000):
        chunk = rows[i : i + 1000]
        stmt = insert(CanonicalPlayer).values(chunk)
        update_cols = {k: getattr(stmt.excluded, k) for k in chunk[0] if k != "sleeper_id"}
        session.execute(stmt.on_conflict_do_update(index_elements=["sleeper_id"], set_=update_cols))
    session.commit()
    cache = DbCache(session)
    cache.set("nfl:players:synced", now.isoformat(), PLAYERS_TTL)
    # Weekly stats join to canonical players; re-join any week loaded before this sync.
    cache.delete_prefix("nfl:week:")
    log.info("players_synced", count=len(rows), duration_ms=round((time.perf_counter() - start) * 1000))
    return len(rows)


def ensure_players_fresh(session: Session, provider: NFLDataProvider | None = None) -> None:
    """Lazy daily refresh. Failures keep serving the existing catalog."""
    if DbCache(session).get("nfl:players:synced") is not None:
        return
    try:
        sync_players(session, provider)
    except AppError as exc:
        log.warning("players_sync_failed", error=exc.code)


def get_current_state(session: Session, provider: NFLDataProvider | None = None) -> NFLState:
    cache = DbCache(session)
    cached = cache.get("nfl:state")
    if cached:
        return NFLState(**cached)
    state = (provider or get_nfl_data_provider()).get_state()
    cache.set("nfl:state", state.model_dump(), STATE_TTL)
    return state


@dataclass
class WeekRefreshResult:
    refreshed: bool
    stats_as_of: datetime | None
    error: AppError | None = None


def _week_key(season: int, week: int) -> str:
    return f"nfl:week:{season}:{week}"


def week_ttl(games: list[NFLGame], now: datetime | None = None) -> int:
    now = now or utcnow()
    for g in games:
        if GameStatus(g.status) in LIVE_STATUSES:
            return LIVE_TTL
        # Keep polling tight around kickoff so games flip to live promptly.
        if g.status in (GameStatus.SCHEDULED, GameStatus.PREGAME) and abs(g.kickoff_at - now) < timedelta(minutes=15):
            return LIVE_TTL
    return IDLE_TTL


def refresh_week(session: Session, season: int, week: int, provider: NFLDataProvider | None = None) -> list[NFLGame]:
    provider = provider or get_nfl_data_provider()
    start = time.perf_counter()
    now = utcnow()

    games_in = provider.get_schedule(season, week)
    if games_in:
        # Upsert: concurrent first loads of the same week must not race on the unique key.
        stmt = insert(NFLGame).values(
            [{"external_game_id": g.external_game_id, **_game_fields(g), "updated_at": now} for g in games_in]
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["external_game_id"],
                set_={k: getattr(stmt.excluded, k) for k in (*_game_fields(games_in[0]), "updated_at")},
            )
        )
        session.commit()

    week_q = select(NFLGame).where(NFLGame.season == season, NFLGame.week == week)
    games = list(session.exec(week_q.execution_options(populate_existing=True)))
    game_by_team: dict[str, int] = {}
    for game in games:
        assert game.id is not None
        game_by_team[game.home_team] = game.id
        game_by_team[game.away_team] = game.id

    stats_in = provider.get_week_stats(season, week)
    sleeper_ids = [s.sleeper_id for s in stats_in]
    id_by_sleeper = dict(
        session.exec(
            select(CanonicalPlayer.sleeper_id, CanonicalPlayer.id).where(
                col(CanonicalPlayer.sleeper_id).in_(sleeper_ids)
            )
        ).all()
    )
    rows = []
    for s in stats_in:
        player_id = id_by_sleeper.get(s.sleeper_id)
        if player_id is None:
            continue
        rows.append(
            {
                "player_id": player_id,
                "season": season,
                "week": week,
                "game_id": game_by_team.get(s.nfl_team or ""),
                "raw_stats_json": s.stats,
                "updated_at": now,
            }
        )
    for i in range(0, len(rows), 1000):
        stmt = insert(PlayerGameStats).values(rows[i : i + 1000])
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["player_id", "season", "week"],
                set_={
                    "raw_stats_json": stmt.excluded.raw_stats_json,
                    "game_id": stmt.excluded.game_id,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
        )
    session.commit()

    DbCache(session).set(_week_key(season, week), now.isoformat(), week_ttl(games, now))
    log.info(
        "nfl_week_refreshed",
        season=season,
        week=week,
        games=len(games),
        stat_rows=len(rows),
        duration_ms=round((time.perf_counter() - start) * 1000),
    )
    return games


def _game_fields(g: NormalizedNFLGame) -> dict[str, object]:
    return {
        "season": g.season,
        "week": g.week,
        "kickoff_at": g.kickoff_at,
        "home_team": g.home_team,
        "away_team": g.away_team,
        "home_score": g.home_score,
        "away_score": g.away_score,
        "status": g.status.value,
        "status_detail": g.status_detail,
        "quarter": g.quarter,
        "clock": g.clock,
        "broadcaster": g.broadcaster,
    }


def ensure_week_fresh(
    session: Session,
    season: int,
    week: int,
    *,
    force: bool = False,
    cache: Cache | None = None,
    provider: NFLDataProvider | None = None,
) -> WeekRefreshResult:
    ensure_players_fresh(session, provider)
    cache = cache or DbCache(session)
    key = _week_key(season, week)
    cached = cache.get(key)
    if cached and not force:
        return WeekRefreshResult(refreshed=False, stats_as_of=datetime.fromisoformat(cached))
    try:
        refresh_week(session, season, week, provider)
        return WeekRefreshResult(refreshed=True, stats_as_of=utcnow())
    except AppError as exc:
        session.rollback()
        last = session.exec(
            select(NFLGame.updated_at)
            .where(NFLGame.season == season, NFLGame.week == week)
            .order_by(col(NFLGame.updated_at).desc())
        ).first()
        return WeekRefreshResult(refreshed=False, stats_as_of=last, error=exc)
