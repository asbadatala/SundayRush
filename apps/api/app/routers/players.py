from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.config import get_settings
from app.db import get_session
from app.domain.models import CanonicalPlayer
from app.errors import NotFound
from app.nfl_data.sync import ensure_players_fresh
from app.player_resolution.names import normalize_name
from app.rate_limit import limiter

router = APIRouter(prefix="/api/players", tags=["players"])

SEARCH_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


class PlayerOut(BaseModel):
    id: int
    full_name: str
    position: str
    nfl_team: str | None
    active_status: str | None
    injury_status: str | None


def player_out(p: CanonicalPlayer) -> PlayerOut:
    assert p.id is not None
    return PlayerOut(
        id=p.id,
        full_name=p.full_name,
        position=p.position,
        nfl_team=p.nfl_team_code,
        active_status=p.active_status,
        injury_status=p.injury_status,
    )


@router.get("/search")
@limiter.limit(get_settings().rate_limit_search)
def search(
    request: Request,
    q: str = Query(min_length=2, max_length=60),
    position: str | None = None,
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_session),
) -> list[PlayerOut]:
    ensure_players_fresh(db)
    needle = normalize_name(q)
    if not needle:
        return []
    similarity = func.similarity(CanonicalPlayer.normalized_name, needle)
    stmt = (
        select(CanonicalPlayer)
        .where(
            col(CanonicalPlayer.position).in_([position.upper()] if position else SEARCH_POSITIONS),
            col(CanonicalPlayer.nfl_team_code).is_not(None),
            or_(
                col(CanonicalPlayer.normalized_name).op("%")(needle),
                col(CanonicalPlayer.normalized_name).contains(needle),
            ),
        )
        .order_by(
            col(CanonicalPlayer.normalized_name).startswith(needle).desc(),
            similarity.desc(),
            func.coalesce(CanonicalPlayer.search_rank, 99999),
        )
        .limit(limit)
    )
    return [player_out(p) for p in db.exec(stmt)]


@router.get("/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_session)) -> PlayerOut:
    p = db.get(CanonicalPlayer, player_id)
    if p is None:
        raise NotFound("That player doesn't exist.")
    return player_out(p)
