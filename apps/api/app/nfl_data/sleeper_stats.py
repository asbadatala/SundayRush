from typing import Any

import httpx

from app.domain.normalized import NormalizedPlayerStats
from app.nfl_data.http import DEFAULT_TIMEOUT, get_json
from app.nfl_data.stat_keys import normalize_sleeper_stats
from app.nfl_data.teams import normalize_team

SLEEPER_STATS_BASE = "https://api.sleeper.com/stats/nfl"


def parse_week_stats(payload: list[dict[str, Any]]) -> list[NormalizedPlayerStats]:
    out: list[NormalizedPlayerStats] = []
    for row in payload:
        player_id = row.get("player_id")
        raw = row.get("stats") or {}
        if not player_id or not raw:
            continue
        stats = normalize_sleeper_stats(raw)
        if not stats and not raw.get("gp"):
            continue
        out.append(
            NormalizedPlayerStats(sleeper_id=str(player_id), nfl_team=normalize_team(row.get("team")), stats=stats)
        )
    return out


class SleeperStatsClient:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def get_week_stats(self, season: int, week: int) -> list[NormalizedPlayerStats]:
        payload = get_json(
            self._client,
            f"{SLEEPER_STATS_BASE}/{season}/{week}",
            params={"season_type": "regular"},
            source="sleeper_stats",
        )
        return parse_week_stats(payload or [])
