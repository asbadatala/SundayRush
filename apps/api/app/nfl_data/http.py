import time
from typing import Any

import httpx

from app.errors import LiveDataUnavailable
from app.logging import log

DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def get_json(client: httpx.Client, url: str, *, source: str, params: dict[str, Any] | None = None) -> Any:
    start = time.perf_counter()
    try:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("nfl_data_fetch_failed", source=source, url=url, error=str(exc))
        raise LiveDataUnavailable() from exc
    finally:
        log.info(
            "nfl_data_fetch",
            source=source,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
        )
