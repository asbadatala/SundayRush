from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.domain.models import User
from app.matchups.service import MatchupDetail, MatchupsResponse, list_matchups, matchup_detail
from app.session import current_user

router = APIRouter(prefix="/api/matchups", tags=["matchups"])


@router.get("")
def matchups(
    season: int | None = None,
    week: int | None = None,
    refresh: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> MatchupsResponse:
    return list_matchups(db, user, season, week, force=refresh)


@router.get("/{matchup_id}")
def detail(matchup_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)) -> MatchupDetail:
    return matchup_detail(db, user, matchup_id)
