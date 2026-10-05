"""Import/sync imported leagues into normalized tables. Provider-agnostic: works against any
FantasyProviderAdapter (Yahoo in P0; Sleeper/ESPN plug in later)."""

import time
from dataclasses import dataclass

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.cache.db_cache import DbCache
from app.domain.models import (
    FantasyLeague,
    FantasyMatchup,
    FantasyTeam,
    RosterEntry,
    RosterSnapshot,
    ScoringProfile,
    User,
    utcnow,
)
from app.domain.normalized import NormalizedFantasyTeam, NormalizedLeague, NormalizedRoster
from app.errors import LeagueNotFound, NotFound, TeamNotSelected, ValidationFailed
from app.logging import log
from app.nfl_data.sync import ensure_players_fresh
from app.player_resolution.resolver import PlayerRef, PlayerResolver
from app.providers.base import FantasyProviderAdapter
from app.providers.yahoo.adapter import yahoo_adapter_for

GAME_DAY_TTL = 5 * 60
IDLE_TTL = 60 * 60


def adapter_for(db: Session, user: User, provider: str) -> FantasyProviderAdapter:
    if provider == "yahoo":
        return yahoo_adapter_for(db, user)
    raise ValidationFailed(f"Provider '{provider}' doesn't support import yet.")


def get_user_league(db: Session, user: User, league_id: int) -> FantasyLeague:
    league = db.get(FantasyLeague, league_id)
    if league is None or league.user_id != user.id:
        raise LeagueNotFound()
    return league


def list_user_leagues(db: Session, user: User) -> list[FantasyLeague]:
    return list(db.exec(select(FantasyLeague).where(FantasyLeague.user_id == user.id).order_by(col(FantasyLeague.id))))


def league_teams(db: Session, league_id: int) -> list[FantasyTeam]:
    return list(db.exec(select(FantasyTeam).where(FantasyTeam.league_id == league_id).order_by(col(FantasyTeam.id))))


@dataclass
class DiscoveredLeague:
    league: NormalizedLeague
    imported_league_id: int | None


def discover(db: Session, user: User, provider: str) -> list[DiscoveredLeague]:
    adapter = adapter_for(db, user, provider)
    start = time.perf_counter()
    leagues = adapter.get_leagues()
    log.info(
        "provider_discover",
        provider=provider,
        leagues=len(leagues),
        duration_ms=round((time.perf_counter() - start) * 1000),
    )
    existing = {lg.external_league_id: lg.id for lg in list_user_leagues(db, user) if lg.provider == provider}
    return [DiscoveredLeague(lg, existing.get(lg.external_league_id)) for lg in leagues]


def _upsert_team(db: Session, user: User, league: FantasyLeague, t: NormalizedFantasyTeam) -> FantasyTeam:
    team = db.exec(
        select(FantasyTeam).where(
            FantasyTeam.league_id == league.id, FantasyTeam.external_team_id == t.external_team_id
        )
    ).first() or FantasyTeam(user_id=user.id, league_id=league.id, provider=league.provider, name=t.name)
    team.external_team_id = t.external_team_id
    team.name = t.name
    team.owner_name = t.owner_name
    team.updated_at = utcnow()
    db.add(team)
    return team


def _save_scoring(db: Session, user: User, league: FantasyLeague, adapter: FantasyProviderAdapter) -> None:
    assert league.external_league_id
    rules = adapter.get_scoring_rules(league.external_league_id)
    profile = (db.get(ScoringProfile, league.scoring_profile_id) if league.scoring_profile_id else None) or (
        ScoringProfile(user_id=user.id, league_id=league.id, name=f"{league.name} scoring")
    )
    profile.scoring_json = rules.rules
    profile.unsupported_json = rules.unsupported
    db.add(profile)
    db.flush()
    league.scoring_profile_id = profile.id


@dataclass
class ImportedLeague:
    league: FantasyLeague
    teams: list[FantasyTeam]
    suggested_team_id: int | None


def import_leagues(db: Session, user: User, provider: str, league_keys: list[str]) -> list[ImportedLeague]:
    if not league_keys:
        raise ValidationFailed("Pick at least one league to import.")
    adapter = adapter_for(db, user, provider)
    available = {lg.external_league_id: lg for lg in adapter.get_leagues()}
    results: list[ImportedLeague] = []
    for key in league_keys:
        meta = available.get(key)
        if meta is None:
            log.warning("provider_import_failed", provider=provider, league=key, code="LEAGUE_NOT_FOUND")
            raise LeagueNotFound(f"League {key} isn't one of your {provider.title()} leagues.")
        start = time.perf_counter()
        league = db.exec(
            select(FantasyLeague).where(
                FantasyLeague.user_id == user.id,
                FantasyLeague.provider == provider,
                FantasyLeague.external_league_id == key,
            )
        ).first() or FantasyLeague(
            user_id=user.id, provider=provider, external_league_id=key, name=meta.name, season=meta.season
        )
        league.name = meta.name
        league.season = meta.season
        league.current_week = meta.current_week
        league.num_teams = meta.num_teams
        league.updated_at = utcnow()
        db.add(league)
        db.flush()

        normalized_teams = adapter.get_teams(key)
        teams = [_upsert_team(db, user, league, t) for t in normalized_teams]
        _save_scoring(db, user, league, adapter)
        db.commit()

        suggested = league.selected_team_id or next(
            (team.id for team, t in zip(teams, normalized_teams, strict=True) if t.is_owned_by_current_user),
            None,
        )
        log.info(
            "provider_import",
            provider=provider,
            league_id=league.id,
            teams=len(teams),
            status="ok",
            duration_ms=round((time.perf_counter() - start) * 1000),
        )
        results.append(ImportedLeague(league, teams, suggested))
    return results


def select_team(db: Session, user: User, league: FantasyLeague, team_id: int, week: int) -> FantasyLeague:
    team = db.get(FantasyTeam, team_id)
    if team is None or team.league_id != league.id:
        raise NotFound("That team isn't in this league.")
    for t in league_teams(db, league.id or 0):
        t.is_user_team = t.id == team_id
        db.add(t)
    league.selected_team_id = team_id
    db.add(league)
    db.commit()
    sync_league(db, user, league, week, force=True)
    return league


def save_roster(
    db: Session, team: FantasyTeam, season: int, week: int, roster: NormalizedRoster, provider: str
) -> RosterSnapshot:
    assert team.id is not None
    snapshot = db.exec(
        select(RosterSnapshot).where(
            RosterSnapshot.fantasy_team_id == team.id, RosterSnapshot.season == season, RosterSnapshot.week == week
        )
    ).first() or RosterSnapshot(fantasy_team_id=team.id, season=season, week=week)
    snapshot.fetched_at = utcnow()
    db.add(snapshot)
    db.flush()
    db.execute(delete(RosterEntry).where(RosterEntry.roster_snapshot_id == snapshot.id))  # type: ignore[arg-type]

    ensure_players_fresh(db)  # resolution needs the canonical catalog
    resolver = PlayerResolver(db)
    unmapped = 0
    for p in roster.players:
        resolution = resolver.resolve(PlayerRef(provider, p.provider_player_id, p.full_name, p.position, p.nfl_team))
        unmapped += resolution.player_id is None
        db.add(
            RosterEntry(
                roster_snapshot_id=snapshot.id or 0,
                player_id=resolution.player_id,
                slot=p.slot,
                is_starter=p.is_starter,
                is_bench=p.is_bench,
                is_ir=p.is_ir,
                provider_player_id=p.provider_player_id,
                provider_player_name=p.full_name,
                provider_position=p.position,
                provider_nfl_team=p.nfl_team,
                provider_status=p.status,
            )
        )
    if unmapped:
        log.warning("roster_unmapped_players", team_id=team.id, count=unmapped)
    return snapshot


def _sync_key(league_id: int, week: int) -> str:
    return f"league:{league_id}:week:{week}"


def sync_league(
    db: Session, user: User, league: FantasyLeague, week: int, *, force: bool = False, game_day: bool = False
) -> bool:
    """Refresh matchup + my roster + opponent roster for `week`. Returns True if fetched."""
    if league.selected_team_id is None:
        raise TeamNotSelected(f"Pick your team in {league.name} to see it on game day.")
    assert league.id is not None
    cache = DbCache(db)
    if not force and cache.get(_sync_key(league.id, week)) is not None:
        return False

    start = time.perf_counter()
    adapter = adapter_for(db, user, league.provider)
    my_team = db.get(FantasyTeam, league.selected_team_id)
    assert my_team is not None and my_team.external_team_id

    teams_by_ext = {t.external_team_id: t for t in league_teams(db, league.id)}
    opponent: FantasyTeam | None = None
    matchup_row: FantasyMatchup | None = None
    for m in adapter.get_matchups(league.external_league_id, week):
        sides = {s.external_team_id: s for s in m.teams}
        if my_team.external_team_id not in sides:
            continue
        mine = sides[my_team.external_team_id]
        other = next((s for k, s in sides.items() if k != my_team.external_team_id), None)
        if other is not None:
            opponent = teams_by_ext.get(other.external_team_id) or _upsert_team(
                db,
                user,
                league,
                NormalizedFantasyTeam(
                    provider=league.provider, external_team_id=other.external_team_id, name=other.name
                ),
            )
            db.flush()
        matchup_row = db.exec(
            select(FantasyMatchup).where(
                FantasyMatchup.league_id == league.id,
                FantasyMatchup.season == league.season,
                FantasyMatchup.week == week,
                FantasyMatchup.user_team_id == my_team.id,
            )
        ).first() or FantasyMatchup(league_id=league.id, season=league.season, week=week, user_team_id=my_team.id or 0)
        matchup_row.opponent_team_id = opponent.id if opponent else None
        matchup_row.user_score = mine.points
        matchup_row.user_projected = mine.projected_points
        matchup_row.opponent_score = other.points if other else None
        matchup_row.opponent_projected = other.projected_points if other else None
        matchup_row.status = m.status
        matchup_row.fetched_at = utcnow()
        db.add(matchup_row)
        break

    save_roster(db, my_team, league.season, week, adapter.get_roster(my_team.external_team_id, week), league.provider)
    if opponent is not None and opponent.external_team_id:
        save_roster(
            db, opponent, league.season, week, adapter.get_roster(opponent.external_team_id, week), league.provider
        )

    league.last_synced_at = utcnow()
    db.add(league)
    db.commit()
    cache.set(_sync_key(league.id, week), league.last_synced_at.isoformat(), GAME_DAY_TTL if game_day else IDLE_TTL)
    log.info(
        "league_refreshed",
        provider=league.provider,
        league_id=league.id,
        week=week,
        has_matchup=matchup_row is not None,
        duration_ms=round((time.perf_counter() - start) * 1000),
    )
    return True


def refresh_league(db: Session, user: User, league: FantasyLeague, week: int) -> None:
    """Explicit refresh: rescan teams + scoring, then roster/matchup bypassing TTL."""
    adapter = adapter_for(db, user, league.provider)
    for t in adapter.get_teams(league.external_league_id):
        _upsert_team(db, user, league, t)
    _save_scoring(db, user, league, adapter)
    db.commit()
    if league.selected_team_id is not None:
        sync_league(db, user, league, week, force=True)


def delete_league(db: Session, league: FantasyLeague) -> None:
    assert league.id is not None
    DbCache(db).delete_prefix(f"league:{league.id}:")
    profile_id = league.scoring_profile_id
    db.delete(league)
    db.flush()
    if profile_id:
        profile = db.get(ScoringProfile, profile_id)
        if profile:
            db.delete(profile)
    db.commit()
