from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.domain.models import User
from app.errors import AppError, app_error_handler
from app.logging import configure_logging, request_logging_middleware
from app.rate_limit import RateLimitExceeded, limiter, rate_limit_handler
from app.routers import game_day, leagues, manual_teams, matchups, players, providers
from app.session import current_user, session_middleware

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)

app = FastAPI(title="SundayRush API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.state.limiter = limiter

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_FAILED", "message": f"{where}: {first.get('msg', 'invalid')}".strip(": ")},
    )


# Order: the last-added middleware runs first. Session must wrap everything else.
app.middleware("http")(request_logging_middleware)
app.middleware("http")(session_middleware)

for r in (providers, leagues, manual_teams, players, game_day, matchups):
    app.include_router(r.router)


@app.get("/api/health")
def health(db: Session = Depends(get_session)) -> dict[str, str]:
    db.execute(text("select 1"))
    return {"status": "ok", "fixture_mode": str(settings.fixture_mode).lower()}


@app.get("/api/session")
def session_info(user: User = Depends(current_user)) -> dict[str, str | bool]:
    """Called once by the web client before anything else so the session cookie exists
    before parallel requests fire (avoids minting two anonymous users)."""
    return {"anonymous": user.email is None}


@app.delete("/api/session")
def clear_session(user: User = Depends(current_user), db: Session = Depends(get_session)) -> dict[str, bool]:
    """'Clear local data': deletes the anonymous user and everything it owns (cascades)."""
    db.delete(user)
    db.commit()
    return {"deleted": True}
