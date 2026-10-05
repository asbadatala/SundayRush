"""Application error hierarchy (spec §19). Serialized as {"code", "message"}."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "Unexpected server error."

    def __init__(self, message: str | None = None, *, http_status: int | None = None):
        self.message = message or self.default_message
        if http_status is not None:
            self.http_status = http_status
        super().__init__(self.message)

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class NotFound(AppError):
    code = "NOT_FOUND"
    http_status = 404
    default_message = "Not found."


class ValidationFailed(AppError):
    code = "VALIDATION_FAILED"
    http_status = 422
    default_message = "The request was invalid."


class LeagueNotFound(AppError):
    code = "LEAGUE_NOT_FOUND"
    http_status = 404
    default_message = "That league could not be found."


class PrivateLeagueUnsupported(AppError):
    code = "PRIVATE_LEAGUE_UNSUPPORTED"
    http_status = 400
    default_message = "Private leagues aren't supported for this provider yet. Create a custom team instead."


class InvalidLeagueId(AppError):
    code = "INVALID_LEAGUE_ID"
    http_status = 400
    default_message = "That league ID is not valid."


class ProviderRateLimited(AppError):
    code = "PROVIDER_RATE_LIMITED"
    http_status = 429
    default_message = "The fantasy provider is rate limiting requests. Try again in a minute."


class ProviderUnavailable(AppError):
    code = "PROVIDER_UNAVAILABLE"
    http_status = 502
    default_message = "The fantasy provider is not responding right now. Try again shortly."


class ProviderAuthRequired(AppError):
    code = "PROVIDER_AUTH_REQUIRED"
    http_status = 401
    default_message = "Sign in with Yahoo to import your leagues."


class ProviderAuthExpired(AppError):
    code = "PROVIDER_AUTH_EXPIRED"
    http_status = 401
    default_message = (
        "Your Yahoo connection has expired. Reconnect Yahoo to refresh your leagues, "
        "or create the roster as a custom team instead."
    )


class TeamNotSelected(AppError):
    code = "TEAM_NOT_SELECTED"
    http_status = 409
    default_message = "Pick your team in this league to see it on game day."


class PlayerMappingFailed(AppError):
    code = "PLAYER_MAPPING_FAILED"
    http_status = 422
    default_message = "Some players could not be matched to NFL players."


class LiveDataUnavailable(AppError):
    code = "LIVE_DATA_UNAVAILABLE"
    http_status = 503
    default_message = "Live NFL data is unavailable right now. Showing the last known stats."


class RateLimited(AppError):
    code = "RATE_LIMITED"
    http_status = 429
    default_message = "Too many requests. Slow down and try again in a moment."


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())
