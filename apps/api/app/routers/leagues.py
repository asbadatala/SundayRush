from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.domain.models import FantasyLeague, FantasyTeam, ScoringProfile, User
from app.nfl_data.sync import get_current_state
from app.providers.sync import (
    delete_league,
    get_user_league,
    import_leagues,
    league_teams,
    list_user_leagues,
    refresh_league,
    select_team,
)
from app.rate_limit import limiter
from app.session import current_user

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


class TeamOut(BaseModel):
    id: int
    external_team_id: str | None
    name: str
    owner_name: str | None
    is_user_team: bool


class LeagueOut(BaseModel):
    id: int
    provider: str
    external_league_id: str
    name: str
    season: int
    current_week: int | None
    num_teams: int | None
    selected_team_id: int | None
    selected_team_name: str | None
    last_synced_at: datetime | None
    scoring_name: str | None
    scoring_rules: dict[str, float]
    unsupported_scoring: list[dict[str, Any]]


def team_out(t: FantasyTeam) -> TeamOut:
    assert t.id is not None
    return TeamOut(
        id=t.id, external_team_id=t.external_team_id, name=t.name, owner_name=t.owner_name, is_user_team=t.is_user_team
    )


def league_out(db: Session, lg: FantasyLeague) -> LeagueOut:
    assert lg.id is not None
    selected = db.get(FantasyTeam, lg.selected_team_id) if lg.selected_team_id else None
    profile = db.get(ScoringProfile, lg.scoring_profile_id) if lg.scoring_profile_id else None
    return LeagueOut(
        id=lg.id,
        provider=lg.provider,
        external_league_id=lg.external_league_id,
        name=lg.name,
        season=lg.season,
        current_week=lg.current_week,
        num_teams=lg.num_teams,
        selected_team_id=lg.selected_team_id,
        selected_team_name=selected.name if selected else None,
        last_synced_at=lg.last_synced_at,
        scoring_name=profile.name if profile else None,
        scoring_rules=profile.scoring_json if profile else {},
        unsupported_scoring=profile.unsupported_json if profile else [],
    )


class ImportRequest(BaseModel):
    provider: str = "yahoo"
    league_ids: list[str] = Field(min_length=1)


class ImportedLeagueOut(BaseModel):
    league: LeagueOut
    teams: list[TeamOut]
    suggested_team_id: int | None


@router.post("/import")
@limiter.limit(get_settings().rate_limit_import)
def import_(
    request: Request, body: ImportRequest, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> list[ImportedLeagueOut]:
    results = import_leagues(db, user, body.provider, body.league_ids)
    return [
        ImportedLeagueOut(
            league=league_out(db, r.league), teams=[team_out(t) for t in r.teams], suggested_team_id=r.suggested_team_id
        )
        for r in results
    ]


@router.get("")
def list_(user: User = Depends(current_user), db: Session = Depends(get_session)) -> list[LeagueOut]:
    return [league_out(db, lg) for lg in list_user_leagues(db, user)]


@router.get("/{league_id}")
def get_(league_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)) -> LeagueOut:
    return league_out(db, get_user_league(db, user, league_id))


@router.get("/{league_id}/teams")
def teams(league_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)) -> list[TeamOut]:
    league = get_user_league(db, user, league_id)
    return [team_out(t) for t in league_teams(db, league.id or 0)]


class SelectTeamRequest(BaseModel):
    team_id: int


@router.post("/{league_id}/select-team")
def select_team_(
    league_id: int, body: SelectTeamRequest, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> LeagueOut:
    league = get_user_league(db, user, league_id)
    week = get_current_state(db).week
    return league_out(db, select_team(db, user, league, body.team_id, week))


@router.post("/{league_id}/refresh")
@limiter.limit(get_settings().rate_limit_import)
def refresh(
    request: Request, league_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> LeagueOut:
    league = get_user_league(db, user, league_id)
    refresh_league(db, user, league, get_current_state(db).week)
    return league_out(db, league)


@router.delete("/{league_id}")
def remove(league_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)) -> dict[str, bool]:
    delete_league(db, get_user_league(db, user, league_id))
    return {"deleted": True}
