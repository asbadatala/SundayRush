"""Persistent domain entities (spec §11)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index, UniqueConstraint, func
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _ts() -> Any:
    """Non-null timestamp defaulting to now."""
    return Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


def _ts_col() -> Any:
    """Nullable timestamp."""
    return Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str | None = Field(default=None, index=True)
    created_at: datetime = _ts()
    updated_at: datetime = _ts()


class ProviderConnection(SQLModel, table=True):
    __tablename__ = "provider_connection"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    provider: str
    external_account_identifier: str | None = None
    encrypted_access_token: str | None = None
    encrypted_refresh_token: str | None = None
    token_expires_at: datetime | None = _ts_col()
    scopes: str | None = None
    created_at: datetime = _ts()
    updated_at: datetime = _ts()


class ScoringProfile(SQLModel, table=True):
    __tablename__ = "scoring_profile"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="user.id", index=True, ondelete="CASCADE")
    league_id: int | None = Field(default=None, index=True)
    name: str
    preset: str | None = None
    scoring_json: dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    # Provider stat categories we could not map to a normalized key.
    unsupported_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class FantasyLeague(SQLModel, table=True):
    __tablename__ = "fantasy_league"
    __table_args__ = (UniqueConstraint("user_id", "provider", "external_league_id"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    provider: str
    external_league_id: str
    name: str
    season: int
    current_week: int | None = None
    num_teams: int | None = None
    scoring_profile_id: int | None = Field(default=None, foreign_key="scoring_profile.id")
    selected_team_id: int | None = None
    last_synced_at: datetime | None = _ts_col()
    created_at: datetime = _ts()
    updated_at: datetime = _ts()


class FantasyTeam(SQLModel, table=True):
    __tablename__ = "fantasy_team"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    league_id: int | None = Field(default=None, foreign_key="fantasy_league.id", index=True, ondelete="CASCADE")
    provider: str
    external_team_id: str | None = None
    name: str
    owner_name: str | None = None
    is_user_team: bool = False
    is_manual: bool = False
    # Manual teams carry their own scoring profile; imported teams use the league's.
    scoring_profile_id: int | None = Field(default=None, foreign_key="scoring_profile.id")
    created_at: datetime = _ts()
    updated_at: datetime = _ts()


class CanonicalPlayer(SQLModel, table=True):
    __tablename__ = "canonical_player"
    __table_args__ = (
        Index(
            "ix_canonical_player_normalized_name_trgm",
            "normalized_name",
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    first_name: str | None = None
    last_name: str | None = None
    full_name: str
    normalized_name: str = Field(index=True)
    position: str = Field(index=True)
    nfl_team_code: str | None = Field(default=None, index=True)
    active_status: str | None = None
    injury_status: str | None = None
    gsis_id: str | None = Field(default=None, index=True)
    sleeper_id: str | None = Field(default=None, unique=True)
    espn_id: str | None = Field(default=None, index=True)
    yahoo_id: str | None = Field(default=None, index=True)
    fleaflicker_id: str | None = None
    stats_provider_id: str | None = None
    search_rank: int | None = None
    updated_at: datetime = _ts()


class PlayerIdMapping(SQLModel, table=True):
    __tablename__ = "player_id_mapping"
    __table_args__ = (UniqueConstraint("provider", "external_id"),)

    id: int | None = Field(default=None, primary_key=True)
    provider: str
    external_id: str
    player_id: int = Field(foreign_key="canonical_player.id", index=True, ondelete="CASCADE")
    method: str  # mapping | provider_id | exact | fuzzy | manual
    confidence: float = 1.0
    created_at: datetime = _ts()


class RosterSnapshot(SQLModel, table=True):
    __tablename__ = "roster_snapshot"
    __table_args__ = (UniqueConstraint("fantasy_team_id", "season", "week"),)

    id: int | None = Field(default=None, primary_key=True)
    fantasy_team_id: int = Field(foreign_key="fantasy_team.id", index=True, ondelete="CASCADE")
    season: int
    week: int
    fetched_at: datetime = _ts()


class RosterEntry(SQLModel, table=True):
    __tablename__ = "roster_entry"

    id: int | None = Field(default=None, primary_key=True)
    roster_snapshot_id: int = Field(foreign_key="roster_snapshot.id", index=True, ondelete="CASCADE")
    # Null when the provider player could not be resolved to a canonical player.
    player_id: int | None = Field(default=None, foreign_key="canonical_player.id")
    slot: str
    is_starter: bool = False
    is_bench: bool = False
    is_ir: bool = False
    provider_player_id: str | None = None
    provider_player_name: str | None = None
    provider_position: str | None = None
    provider_nfl_team: str | None = None
    provider_status: str | None = None


class FantasyMatchup(SQLModel, table=True):
    __tablename__ = "fantasy_matchup"
    __table_args__ = (UniqueConstraint("league_id", "season", "week", "user_team_id"),)

    id: int | None = Field(default=None, primary_key=True)
    league_id: int = Field(foreign_key="fantasy_league.id", index=True, ondelete="CASCADE")
    season: int
    week: int
    user_team_id: int = Field(foreign_key="fantasy_team.id", ondelete="CASCADE")
    opponent_team_id: int | None = Field(default=None, foreign_key="fantasy_team.id", ondelete="SET NULL")
    user_score: float | None = None
    opponent_score: float | None = None
    user_projected: float | None = None
    opponent_projected: float | None = None
    status: str | None = None
    fetched_at: datetime = _ts()


class NFLGame(SQLModel, table=True):
    __tablename__ = "nfl_game"
    __table_args__ = (Index("ix_nfl_game_season_week", "season", "week"),)

    id: int | None = Field(default=None, primary_key=True)
    external_game_id: str = Field(unique=True)
    season: int
    week: int
    kickoff_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    home_team: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None
    status: str
    status_detail: str | None = None
    quarter: int | None = None
    clock: str | None = None
    broadcaster: str | None = None
    updated_at: datetime = _ts()


class PlayerGameStats(SQLModel, table=True):
    __tablename__ = "player_game_stats"
    __table_args__ = (UniqueConstraint("player_id", "season", "week"),)

    id: int | None = Field(default=None, primary_key=True)
    game_id: int | None = Field(default=None, foreign_key="nfl_game.id", index=True, ondelete="SET NULL")
    player_id: int = Field(foreign_key="canonical_player.id", index=True, ondelete="CASCADE")
    season: int
    week: int
    raw_stats_json: dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    updated_at: datetime = _ts()


class CacheEntry(SQLModel, table=True):
    __tablename__ = "cache_entry"

    key: str = Field(primary_key=True)
    value: Any = Field(default=None, sa_column=Column(JSON, nullable=True))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = _ts()
