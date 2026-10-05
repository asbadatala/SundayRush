from datetime import datetime
from typing import Any

import httpx

from app.domain.normalized import GameStatus, NormalizedNFLGame
from app.logging import log
from app.nfl_data.http import DEFAULT_TIMEOUT, get_json
from app.nfl_data.teams import normalize_team

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

_STATUS_BY_NAME = {
    "STATUS_SCHEDULED": GameStatus.SCHEDULED,
    "STATUS_PREGAME": GameStatus.PREGAME,
    "STATUS_IN_PROGRESS": GameStatus.LIVE,
    "STATUS_END_PERIOD": GameStatus.LIVE,
    "STATUS_DELAYED": GameStatus.LIVE,
    "STATUS_HALFTIME": GameStatus.HALFTIME,
    "STATUS_FINAL": GameStatus.FINAL,
    "STATUS_FINAL_OVERTIME": GameStatus.FINAL,
    "STATUS_FINAL_OT": GameStatus.FINAL,
    "STATUS_END_OF_GAME": GameStatus.FINAL,
    "STATUS_POSTPONED": GameStatus.POSTPONED,
    "STATUS_CANCELED": GameStatus.CANCELED,
    "STATUS_CANCELLED": GameStatus.CANCELED,
    "STATUS_SUSPENDED": GameStatus.POSTPONED,
}
_STATUS_BY_STATE = {"pre": GameStatus.SCHEDULED, "in": GameStatus.LIVE, "post": GameStatus.FINAL}


def map_status(status_type: dict[str, Any]) -> GameStatus:
    name = status_type.get("name") or ""
    if name in _STATUS_BY_NAME:
        return _STATUS_BY_NAME[name]
    fallback = _STATUS_BY_STATE.get(status_type.get("state") or "", GameStatus.SCHEDULED)
    log.warning("espn_unknown_status", name=name, mapped=fallback.value)
    return fallback


def _broadcaster(competition: dict[str, Any]) -> str | None:
    for b in competition.get("broadcasts") or []:
        names = b.get("names") or []
        if names:
            return ", ".join(names)
    for gb in competition.get("geoBroadcasts") or []:
        name = (gb.get("media") or {}).get("shortName")
        if name:
            return str(name)
    return None


def _score(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_scoreboard(payload: dict[str, Any], season: int, week: int) -> list[NormalizedNFLGame]:
    games: list[NormalizedNFLGame] = []
    for event in payload.get("events") or []:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        status_block = event.get("status") or competition.get("status") or {}
        status = map_status(status_block.get("type") or {})
        has_score = status in (GameStatus.LIVE, GameStatus.HALFTIME, GameStatus.FINAL)
        in_game = status in (GameStatus.LIVE, GameStatus.HALFTIME)
        games.append(
            NormalizedNFLGame(
                external_game_id=str(event["id"]),
                season=season,
                week=week,
                kickoff_at=datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
                home_team=normalize_team(home["team"]["abbreviation"]) or home["team"]["abbreviation"],
                away_team=normalize_team(away["team"]["abbreviation"]) or away["team"]["abbreviation"],
                home_score=_score(home.get("score")) if has_score else None,
                away_score=_score(away.get("score")) if has_score else None,
                status=status,
                status_detail=(status_block.get("type") or {}).get("shortDetail"),
                quarter=status_block.get("period") if in_game else None,
                clock=status_block.get("displayClock") if in_game else None,
                broadcaster=_broadcaster(competition),
            )
        )
    return games


class ESPNScheduleClient:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def get_schedule(self, season: int, week: int) -> list[NormalizedNFLGame]:
        payload = get_json(
            self._client,
            ESPN_SCOREBOARD,
            params={"dates": season, "seasontype": 2, "week": week},
            source="espn_scoreboard",
        )
        return parse_scoreboard(payload, season, week)
