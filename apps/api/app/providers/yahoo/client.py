"""HTTP client for fantasysports.yahooapis.com/fantasy/v2 (JSON format)."""

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.errors import LeagueNotFound, ProviderAuthExpired, ProviderRateLimited, ProviderUnavailable
from app.logging import log

BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2/"
RETRY_STATUSES = {429, 999}  # Yahoo signals throttling with 999
BACKOFF_SECONDS = (0.5, 1.5, 3.0)


class YahooHttp(Protocol):
    def get(self, path: str) -> Any: ...


class YahooClient:
    def __init__(
        self,
        get_token: Callable[[bool], str],
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        """`get_token(force_refresh)` returns a valid access token."""
        self._get_token = get_token
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=20.0)
        self._sleep = sleep

    def get(self, path: str) -> Any:
        token = self._get_token(False)
        refreshed = False
        attempt = 0
        while True:
            start = time.perf_counter()
            try:
                resp = self._http.get(path, params={"format": "json"}, headers={"Authorization": f"Bearer {token}"})
            except httpx.HTTPError as exc:
                log.warning("yahoo_request_failed", path=path, error=type(exc).__name__)
                raise ProviderUnavailable("Yahoo is not responding right now. Try again shortly.") from exc
            log.info(
                "yahoo_request",
                path=path,
                status=resp.status_code,
                latency_ms=round((time.perf_counter() - start) * 1000, 1),
            )
            if resp.status_code == 401 and not refreshed:
                token = self._get_token(True)
                refreshed = True
                continue
            if resp.status_code == 401:
                raise ProviderAuthExpired()
            if resp.status_code in RETRY_STATUSES:
                log.warning("yahoo_rate_limited", path=path, attempt=attempt)
                if attempt >= len(BACKOFF_SECONDS):
                    raise ProviderRateLimited("Yahoo is rate limiting requests. Try again in a minute.")
                self._sleep(BACKOFF_SECONDS[attempt])
                attempt += 1
                continue
            if resp.status_code in (400, 404):
                raise LeagueNotFound("Yahoo couldn't find that league or team.")
            if resp.status_code >= 500:
                raise ProviderUnavailable("Yahoo is not responding right now. Try again shortly.")
            if resp.status_code >= 400:
                log.warning("yahoo_request_rejected", path=path, status=resp.status_code, reason=_yahoo_error(resp))
                if resp.status_code == 403:
                    # Seen when the Yahoo app itself lacks the Fantasy Sports permission.
                    raise ProviderUnavailable(
                        "Yahoo says this app isn't authorized for Fantasy Sports. Check that the Yahoo app has "
                        "the Fantasy Sports (Read) permission, then reconnect Yahoo."
                    )
                raise ProviderUnavailable(f"Yahoo returned an error ({resp.status_code}).")
            try:
                return resp.json()
            except ValueError as exc:
                raise ProviderUnavailable("Yahoo returned an unreadable response.") from exc


def _yahoo_error(resp: httpx.Response) -> str | None:
    try:
        return str(resp.json()["error"]["description"])[:300]
    except (ValueError, KeyError, TypeError):
        return resp.text[:300] or None


def fixture_name(path: str) -> str:
    return re.sub(r"[/;=,]+", "_", path.strip("/")) + ".json"


class FixtureYahooClient:
    """FIXTURE_MODE: serves recorded Yahoo responses from tests/fixtures/yahoo/."""

    def __init__(self, root: Path, get_token: Callable[[bool], str]):
        self.root = root
        self._get_token = get_token

    def get(self, path: str) -> Any:
        self._get_token(False)  # exercises token refresh/expiry just like the real client
        file = self.root / fixture_name(path)
        if not file.exists():
            # Rosters/scoreboards fall back to a week-agnostic fixture.
            generic = self.root / fixture_name(re.sub(r";week=\d+", "", path))
            if not generic.exists():
                log.warning("yahoo_fixture_missing", path=path, file=file.name)
                raise LeagueNotFound("Yahoo couldn't find that league or team.")
            file = generic
        return json.loads(file.read_text())
