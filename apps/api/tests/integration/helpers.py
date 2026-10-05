from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

SEASON, WEEK = 2026, 4
A, B = "461.l.1001", "461.l.2002"


def connect_yahoo_fixture(client: TestClient) -> None:
    """FIXTURE_MODE OAuth: start redirects straight to our callback with a fake code."""
    start = client.get("/api/providers/yahoo/auth/start", follow_redirects=False)
    assert start.status_code == 302
    callback = urlparse(start.headers["location"])
    assert callback.path == "/api/providers/yahoo/auth/callback"
    done = client.get(f"{callback.path}?{callback.query}", follow_redirects=False)
    assert done.status_code == 302 and done.headers["location"] == "/teams/yahoo/select"


def import_and_select(client: TestClient, keys: list[str]) -> list[dict[str, Any]]:
    imported = client.post("/api/leagues/import", json={"provider": "yahoo", "league_ids": keys})
    assert imported.status_code == 200, imported.text
    out = []
    for item in imported.json():
        assert item["suggested_team_id"] is not None
        sel = client.post(
            f"/api/leagues/{item['league']['id']}/select-team", json={"team_id": item["suggested_team_id"]}
        )
        assert sel.status_code == 200, sel.text
        out.append(sel.json())
    return out


def game_day(client: TestClient, **params: Any) -> dict[str, Any]:
    resp = client.get("/api/game-day", params={"season": SEASON, "week": WEEK, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def find_game(data: dict[str, Any], away: str, home: str) -> dict[str, Any]:
    return next(g for g in data["games"] if g["game"]["away_team"] == away and g["game"]["home_team"] == home)


def query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)
