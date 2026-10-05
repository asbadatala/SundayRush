"""Anonymous server-side session.

The first request gets an `ff_session` cookie (HTTP-only, Secure, SameSite=Lax) holding a
signed opaque user id. An anonymous `User` row is created lazily for it, and every query is
scoped by that user id.
"""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, Request, Response
from itsdangerous import BadSignature, URLSafeSerializer, URLSafeTimedSerializer
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.domain.models import User

SESSION_COOKIE = "ff_session"
OAUTH_STATE_COOKIE = "ff_oauth_state"
SESSION_MAX_AGE = 400 * 24 * 3600  # browsers cap cookie lifetime at ~400 days
OAUTH_STATE_MAX_AGE = 600


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().session_secret, salt="ff_session")


def _state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="ff_oauth_state")


def sign_user_id(user_id: str) -> str:
    return _serializer().dumps(user_id)


def unsign_user_id(token: str | None) -> str | None:
    if not token:
        return None
    try:
        value = _serializer().loads(token)
    except BadSignature:
        return None
    return value if isinstance(value, str) else None


def set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )


async def session_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    user_id = unsign_user_id(request.cookies.get(SESSION_COOKIE))
    is_new = user_id is None
    request.state.user_id = user_id or str(uuid.uuid4())
    response = await call_next(request)
    if is_new:
        set_cookie(response, SESSION_COOKIE, sign_user_id(request.state.user_id), SESSION_MAX_AGE)
    return response


def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    user_id: str = request.state.user_id
    user = db.get(User, user_id)
    if user is None:
        db.execute(insert(User).values(id=user_id).on_conflict_do_nothing(index_elements=["id"]))
        db.commit()
        user = db.get(User, user_id)
        assert user is not None
    return user


def make_oauth_state(response: Response) -> str:
    state = uuid.uuid4().hex
    set_cookie(response, OAUTH_STATE_COOKIE, _state_serializer().dumps(state), OAUTH_STATE_MAX_AGE)
    return state


def verify_oauth_state(request: Request, state: str | None) -> bool:
    token = request.cookies.get(OAUTH_STATE_COOKIE)
    if not token or not state:
        return False
    try:
        expected = _state_serializer().loads(token, max_age=OAUTH_STATE_MAX_AGE)
    except BadSignature:
        return False
    return isinstance(expected, str) and expected == state
