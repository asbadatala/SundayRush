from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.cache.db_cache import DbCache
from app.config import get_settings
from app.crypto import encrypt
from app.db import get_session
from app.domain.models import User, utcnow
from app.errors import AppError, NotFound
from app.logging import log
from app.providers.sync import discover, list_user_leagues
from app.providers.yahoo.oauth import (
    FakeYahooOAuth,
    delete_connection,
    get_connection,
    get_oauth_client,
    store_tokens,
)
from app.rate_limit import limiter
from app.session import OAUTH_STATE_COOKIE, current_user, make_oauth_state, verify_oauth_state

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderOut(BaseModel):
    id: str
    name: str
    available: bool
    connected: bool = False
    connected_at: datetime | None = None
    note: str | None = None


@router.get("")
def list_providers(user: User = Depends(current_user), db: Session = Depends(get_session)) -> list[ProviderOut]:
    conn = get_connection(db, user)
    return [
        ProviderOut(
            id="yahoo",
            name="Yahoo",
            available=True,
            connected=conn is not None,
            connected_at=conn.created_at if conn else None,
        ),
        ProviderOut(id="manual", name="Custom Team", available=True),
        ProviderOut(id="sleeper", name="Sleeper", available=False, note="Coming soon — use a Custom Team for now."),
        ProviderOut(id="espn", name="ESPN", available=False, note="Coming soon — use a Custom Team for now."),
    ]


@router.get("/yahoo/auth/start")
def yahoo_auth_start(user: User = Depends(current_user)) -> RedirectResponse:
    response = RedirectResponse("about:blank", status_code=302)
    state = make_oauth_state(response)
    try:
        url = get_oauth_client().authorize_url(state)
    except AppError as exc:
        return RedirectResponse(f"/teams/new?error={exc.code}", status_code=302)
    response.headers["location"] = url
    log.info("yahoo_auth_start", user_id=user.id)
    return response


@router.get("/yahoo/auth/callback")
def yahoo_auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> RedirectResponse:
    def fail(code_: str) -> RedirectResponse:
        resp = RedirectResponse(f"/teams/new?error={code_}", status_code=302)
        resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        return resp

    if error:
        log.info("yahoo_auth_denied", user_id=user.id)
        return fail("PROVIDER_AUTH_REQUIRED")
    if not verify_oauth_state(request, state):
        log.warning("yahoo_auth_bad_state", user_id=user.id)
        return fail("OAUTH_STATE_INVALID")
    if not code:
        return fail("PROVIDER_AUTH_REQUIRED")
    try:
        tokens = get_oauth_client().exchange_code(code)
    except AppError as exc:
        log.warning("yahoo_auth_exchange_failed", user_id=user.id, code=exc.code)
        return fail(exc.code)
    store_tokens(db, user, tokens)
    log.info("yahoo_auth_connected", user_id=user.id)
    resp = RedirectResponse("/teams/yahoo/select", status_code=302)
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return resp


class DiscoveredLeagueOut(BaseModel):
    external_league_id: str
    name: str
    season: int
    num_teams: int | None
    scoring_type: str | None
    imported_league_id: int | None


@router.post("/yahoo/discover")
@limiter.limit(get_settings().rate_limit_import)
def yahoo_discover(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> list[DiscoveredLeagueOut]:
    return [
        DiscoveredLeagueOut(
            external_league_id=d.league.external_league_id,
            name=d.league.name,
            season=d.league.season,
            num_teams=d.league.num_teams,
            scoring_type=d.league.scoring_type,
            imported_league_id=d.imported_league_id,
        )
        for d in discover(db, user, "yahoo")
    ]


@router.delete("/yahoo/connection")
def yahoo_disconnect(user: User = Depends(current_user), db: Session = Depends(get_session)) -> dict[str, bool]:
    deleted = delete_connection(db, user)
    log.info("yahoo_disconnected", user_id=user.id, deleted=deleted)
    return {"deleted": deleted}


# --- FIXTURE_MODE only: simulate a revoked Yahoo refresh token (spec §23 UI flow 9) ---------


@router.post("/yahoo/_fixture/expire", include_in_schema=False)
def fixture_expire(user: User = Depends(current_user), db: Session = Depends(get_session)) -> dict[str, bool]:
    if not get_settings().fixture_mode:
        raise NotFound()
    conn = get_connection(db, user)
    if conn is None:
        raise NotFound()
    conn.encrypted_refresh_token = encrypt(FakeYahooOAuth.REVOKED)
    conn.token_expires_at = utcnow()
    db.add(conn)
    db.commit()
    cache = DbCache(db)
    for league in list_user_leagues(db, user):
        cache.delete_prefix(f"league:{league.id}:")
    return {"expired": True}
