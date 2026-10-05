from typing import Any

import httpx

from app.domain.normalized import NFLState, NormalizedNFLPlayer
from app.nfl_data.http import get_json
from app.nfl_data.teams import normalize_team

SLEEPER_BASE = "https://api.sleeper.app/v1"
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def _str_or_none(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def parse_players(payload: dict[str, dict[str, Any]]) -> list[NormalizedNFLPlayer]:
    players: list[NormalizedNFLPlayer] = []
    for sleeper_id, p in payload.items():
        position = p.get("position")
        if position not in FANTASY_POSITIONS:
            continue
        first, last = p.get("first_name"), p.get("last_name")
        full = p.get("full_name") or " ".join(x for x in (first, last) if x)
        if not full:
            continue
        players.append(
            NormalizedNFLPlayer(
                sleeper_id=str(p.get("player_id") or sleeper_id),
                first_name=first,
                last_name=last,
                full_name=full,
                position=position,
                nfl_team=normalize_team(p.get("team")),
                active_status=p.get("status") or ("Active" if p.get("active") else None),
                injury_status=p.get("injury_status"),
                gsis_id=_str_or_none(p.get("gsis_id")),
                espn_id=_str_or_none(p.get("espn_id")),
                yahoo_id=_str_or_none(p.get("yahoo_id")),
                stats_provider_id=_str_or_none(p.get("sportradar_id")),
                search_rank=p.get("search_rank"),
            )
        )
    return players


def parse_state(payload: dict[str, Any]) -> NFLState:
    return NFLState(
        season=int(payload["season"]),
        week=max(1, int(payload.get("display_week") or payload.get("week") or 1)),
        season_type=payload.get("season_type") or "regular",
    )


class SleeperPlayersClient:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0))

    def get_players(self) -> list[NormalizedNFLPlayer]:
        return parse_players(get_json(self._client, f"{SLEEPER_BASE}/players/nfl", source="sleeper_players"))

    def get_state(self) -> NFLState:
        return parse_state(get_json(self._client, f"{SLEEPER_BASE}/state/nfl", source="sleeper_state"))
