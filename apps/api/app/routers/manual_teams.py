from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db import get_session
from app.domain.models import CanonicalPlayer, FantasyTeam, RosterEntry, ScoringProfile, User
from app.game_day.contexts import manual_teams
from app.nfl_data.sync import get_current_state
from app.providers.manual.adapter import (
    add_player,
    create_manual_team,
    get_manual_team,
    latest_snapshot,
    remove_player,
    update_manual_team,
)
from app.routers.players import PlayerOut, player_out
from app.session import current_user

router = APIRouter(prefix="/api/manual-teams", tags=["manual-teams"])

Preset = Literal["standard", "half_ppr", "ppr"]


class RosterPlayerOut(BaseModel):
    player: PlayerOut
    slot: str
    is_starter: bool
    is_bench: bool


class ManualTeamOut(BaseModel):
    id: int
    name: str
    preset: str | None
    scoring_name: str | None
    updated_at: datetime
    starters: list[RosterPlayerOut]
    bench: list[RosterPlayerOut]


def team_out(db: Session, team: FantasyTeam) -> ManualTeamOut:
    assert team.id is not None
    profile = db.get(ScoringProfile, team.scoring_profile_id) if team.scoring_profile_id else None
    snapshot = latest_snapshot(db, team.id)
    rows: list[RosterPlayerOut] = []
    if snapshot:
        for entry, player in db.exec(
            select(RosterEntry, CanonicalPlayer)
            .join(CanonicalPlayer, CanonicalPlayer.id == RosterEntry.player_id)  # type: ignore[arg-type]
            .where(RosterEntry.roster_snapshot_id == snapshot.id)
            .order_by(RosterEntry.id)  # type: ignore[arg-type]
        ):
            rows.append(
                RosterPlayerOut(
                    player=player_out(player), slot=entry.slot, is_starter=entry.is_starter, is_bench=entry.is_bench
                )
            )
    return ManualTeamOut(
        id=team.id,
        name=team.name,
        preset=profile.preset if profile else None,
        scoring_name=profile.name if profile else None,
        updated_at=team.updated_at,
        starters=[r for r in rows if r.is_starter],
        bench=[r for r in rows if not r.is_starter],
    )


class PlayerSlot(BaseModel):
    player_id: int
    slot: Literal["starter", "bench"] = "starter"


class CreateManualTeam(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    preset: Preset = "ppr"
    players: list[PlayerSlot] = Field(default_factory=list)


class UpdateManualTeam(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    preset: Preset | None = None


@router.post("")
def create(
    body: CreateManualTeam, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> ManualTeamOut:
    state = get_current_state(db)
    team = create_manual_team(db, user, body.name, body.preset, state.season, state.week)
    for p in body.players:
        add_player(db, team, p.player_id, p.slot)
    return team_out(db, team)


@router.get("")
def list_(user: User = Depends(current_user), db: Session = Depends(get_session)) -> list[ManualTeamOut]:
    return [team_out(db, t) for t in manual_teams(db, user)]


@router.get("/{team_id}")
def get_(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)) -> ManualTeamOut:
    return team_out(db, get_manual_team(db, user, team_id))


@router.patch("/{team_id}")
def update(
    team_id: int, body: UpdateManualTeam, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> ManualTeamOut:
    team = update_manual_team(db, get_manual_team(db, user, team_id), body.name, body.preset)
    return team_out(db, team)


@router.delete("/{team_id}")
def delete(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)) -> dict[str, bool]:
    team = get_manual_team(db, user, team_id)
    profile_id = team.scoring_profile_id
    db.delete(team)
    db.flush()
    if profile_id and (profile := db.get(ScoringProfile, profile_id)):
        db.delete(profile)
    db.commit()
    return {"deleted": True}


@router.post("/{team_id}/players")
def add(
    team_id: int, body: PlayerSlot, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> ManualTeamOut:
    team = get_manual_team(db, user, team_id)
    add_player(db, team, body.player_id, body.slot)
    return team_out(db, team)


@router.delete("/{team_id}/players/{player_id}")
def remove(
    team_id: int, player_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> ManualTeamOut:
    team = get_manual_team(db, user, team_id)
    remove_player(db, team, player_id)
    return team_out(db, team)
