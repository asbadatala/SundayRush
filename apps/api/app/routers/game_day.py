from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.domain.models import User
from app.game_day.schemas import GameDayResponse
from app.game_day.service import build_game_day
from app.nfl_data.sync import get_current_state
from app.session import current_user

router = APIRouter(prefix="/api", tags=["game-day"])


@router.get("/game-day")
def game_day(
    season: int | None = None,
    week: int | None = None,
    refresh: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> GameDayResponse:
    return build_game_day(db, user, season, week, force=refresh)


class StateOut(BaseModel):
    season: int
    week: int
    season_type: str


@router.get("/nfl/state")
def nfl_state(db: Session = Depends(get_session)) -> StateOut:
    s = get_current_state(db)
    return StateOut(season=s.season, week=s.week, season_type=s.season_type)
