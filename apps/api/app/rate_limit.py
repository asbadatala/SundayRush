from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.errors import RateLimited


def _session_key(request: Request) -> str:
    # Rate-limit per anonymous session; fall back to client IP.
    return getattr(request.state, "user_id", None) or (request.client.host if request.client else "anon")


limiter = Limiter(key_func=_session_key)


async def rate_limit_handler(_: Request, __: Exception) -> JSONResponse:
    err = RateLimited()
    return JSONResponse(status_code=err.http_status, content=err.to_dict())


__all__ = ["limiter", "rate_limit_handler", "RateLimitExceeded"]
