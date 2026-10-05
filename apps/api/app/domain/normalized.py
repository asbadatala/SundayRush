"""Provider-agnostic types returned by adapters. Nothing outside providers/ and nfl_data/
sees raw provider payloads — only these."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GameStatus(StrEnum):
    SCHEDULED = "scheduled"
    PREGAME = "pregame"
    LIVE = "live"
    HALFTIME = "halftime"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELED = "canceled"


LIVE_STATUSES = {GameStatus.LIVE, GameStatus.HALFTIME}


class NormalizedScoringRules(BaseModel):
    """Normalized stat key -> points per unit."""

    rules: dict[str, float] = Field(default_factory=dict)
    # Provider stat categories that have no normalized equivalent (e.g., yardage bonuses).
    unsupported: list[dict[str, Any]] = Field(default_factory=list)


class NormalizedLeague(BaseModel):
    provider: str
    external_league_id: str
    name: str
    season: int
    current_week: int | None = None
    num_teams: int | None = None
    scoring_type: str | None = None


class NormalizedFantasyTeam(BaseModel):
    provider: str
    external_team_id: str
    name: str
    owner_name: str | None = None
    is_owned_by_current_user: bool = False


class NormalizedRosterPlayer(BaseModel):
    provider_player_id: str
    full_name: str
    position: str
    nfl_team: str | None = None
    slot: str
    is_starter: bool
    is_bench: bool
    is_ir: bool = False
    status: str | None = None


class NormalizedRoster(BaseModel):
    external_team_id: str
    week: int
    players: list[NormalizedRosterPlayer]


class NormalizedMatchupSide(BaseModel):
    external_team_id: str
    name: str
    points: float | None = None
    projected_points: float | None = None


class NormalizedMatchup(BaseModel):
    week: int
    status: str | None = None
    teams: list[NormalizedMatchupSide]


class NormalizedNFLPlayer(BaseModel):
    sleeper_id: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str
    position: str
    nfl_team: str | None = None
    active_status: str | None = None
    injury_status: str | None = None
    gsis_id: str | None = None
    espn_id: str | None = None
    yahoo_id: str | None = None
    stats_provider_id: str | None = None
    search_rank: int | None = None


class NormalizedNFLGame(BaseModel):
    external_game_id: str
    season: int
    week: int
    kickoff_at: datetime
    home_team: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None
    status: GameStatus
    status_detail: str | None = None
    quarter: int | None = None
    clock: str | None = None
    broadcaster: str | None = None


class NormalizedPlayerStats(BaseModel):
    sleeper_id: str
    nfl_team: str | None = None
    stats: dict[str, float]


class NFLState(BaseModel):
    season: int
    week: int
    season_type: str = "regular"
