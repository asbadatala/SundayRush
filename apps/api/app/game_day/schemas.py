from datetime import datetime

from pydantic import BaseModel

from app.game_day.ownership import Ownership


class GameOut(BaseModel):
    id: int
    external_game_id: str
    kickoff_at: datetime
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    status: str
    status_detail: str | None
    quarter: int | None
    clock: str | None
    broadcaster: str | None


class PlayerRow(BaseModel):
    key: str
    player_id: int | None
    name: str
    position: str
    nfl_team: str | None
    league_id: int | None
    league_name: str
    team_id: int
    team_name: str
    provider: str
    ownership: Ownership
    slot: str
    points: float | None
    points_unavailable_reason: str | None = None
    injury_status: str | None = None
    stat_line: str | None = None
    mapped: bool = True
    game_id: int | None = None
    game_status: str | None = None


class GameGroup(BaseModel):
    game: GameOut
    my_starters: list[PlayerRow]
    my_bench: list[PlayerRow]
    opponents: list[PlayerRow]


class NoGameGroup(BaseModel):
    """Players on bye, free agents, or unmapped provider players."""

    my_starters: list[PlayerRow]
    my_bench: list[PlayerRow]
    opponents: list[PlayerRow]


class LeagueError(BaseModel):
    league_id: int | None
    league_name: str
    provider: str
    code: str
    message: str


class GameDayResponse(BaseModel):
    season: int
    week: int
    generated_at: datetime
    stats_as_of: datetime | None
    live_data_available: bool
    any_live: bool
    has_teams: bool
    team_count: int
    games: list[GameGroup]
    no_game: NoGameGroup
    league_errors: list[LeagueError]
