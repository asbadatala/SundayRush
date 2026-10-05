"""Import fixture Yahoo leagues -> normalize -> select team -> matchups -> grouped game-day."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.domain.models import FantasyLeague, ScoringProfile
from app.domain.normalized import NFLState
from app.errors import LiveDataUnavailable, ProviderUnavailable
from app.nfl_data.composite import set_nfl_data_provider
from app.providers.yahoo.client import FixtureYahooClient
from tests.conftest import player_id
from tests.integration.helpers import A, B, connect_yahoo_fixture, find_game, game_day, import_and_select


@pytest.fixture
def two_leagues(client: TestClient) -> TestClient:
    connect_yahoo_fixture(client)
    discovered = client.post("/api/providers/yahoo/discover").json()
    assert [d["external_league_id"] for d in discovered] == [A, B]
    import_and_select(client, [A, B])
    return client


def rows(group: dict[str, Any], kind: str) -> list[tuple[str, str]]:
    return [(r["name"], r["league_name"]) for r in group[kind]]


def test_import_normalizes_league_teams_and_scoring(two_leagues: TestClient, db: Session) -> None:
    leagues = two_leagues.get("/api/leagues").json()
    assert [(lg["name"], lg["selected_team_name"]) for lg in leagues] == [
        ("Sunday Funday", "Ankit's Aces"),
        ("Work League", "Office Kings"),
    ]
    assert leagues[0]["scoring_rules"]["reception"] == 1
    assert leagues[1]["scoring_rules"]["reception"] == 0.5
    assert leagues[1]["scoring_rules"]["pass_td"] == 6
    teams = two_leagues.get(f"/api/leagues/{leagues[0]['id']}/teams").json()
    assert len(teams) == 4 and sum(t["is_user_team"] for t in teams) == 1
    assert all(lg["last_synced_at"] for lg in leagues)

    # Re-importing is idempotent.
    two_leagues.post("/api/leagues/import", json={"provider": "yahoo", "league_ids": [A]})
    assert len(db.exec(select(FantasyLeague)).all()) == 2
    assert len(db.exec(select(ScoringProfile)).all()) == 2


def test_game_day_groups_by_game_with_league_specific_scoring(two_leagues: TestClient, db: Session) -> None:
    data = game_day(two_leagues)
    assert data["league_errors"] == []
    assert data["live_data_available"] is True and data["has_teams"] and data["team_count"] == 2
    assert len(data["games"]) == 16

    # Live games sort before upcoming, upcoming before final.
    statuses = [g["game"]["status"] for g in data["games"]]
    rank = {"live": 0, "halftime": 0, "scheduled": 1, "final": 2}
    assert [rank[s] for s in statuses] == sorted(rank[s] for s in statuses)

    # Josh Allen: my starter in League A, opponent's starter in League B, scored per league.
    buf = find_game(data, "NE", "BUF")
    assert ("Josh Allen", "Sunday Funday") in rows(buf, "my_starters")
    assert ("Josh Allen", "Work League") in rows(buf, "opponents")
    allen_a = next(r for r in buf["my_starters"] if r["name"] == "Josh Allen")
    allen_b = next(r for r in buf["opponents"] if r["name"] == "Josh Allen")
    # 253 pass yds, 1 pass TD, 1 INT, 4 rush yds, 1 rush TD
    assert allen_a["points"] == 19.52  # pass TD 4, INT -1
    assert allen_b["points"] == 20.52  # pass TD 6, INT -2
    assert allen_a["ownership"] == "MY_STARTER" and allen_b["ownership"] == "OPPONENT"
    assert allen_a["stat_line"].startswith("23/33")
    assert rows(buf, "my_bench") == [("Drake Maye", "Work League")]
    # Defense rows render with points unavailable rather than disappearing.
    bills = next(r for r in buf["my_starters"] if r["position"] == "DEF")
    assert bills["points"] is None and "DEF" in bills["points_unavailable_reason"]

    # Bench: Justin Jefferson (Q) is on my League A bench.
    min_game = find_game(data, "MIA", "MIN")
    jj = next(r for r in min_game["my_bench"] if r["name"] == "Justin Jefferson")
    assert jj["ownership"] == "MY_BENCH" and jj["injury_status"] == "Q"

    # Kyren Williams: opponent starter in A, my starter in B — both contexts present.
    lar = find_game(data, "LAR", "PHI")
    assert ("Kyren Williams", "Work League") in rows(lar, "my_starters")
    assert ("Kyren Williams", "Sunday Funday") in rows(lar, "opponents")

    # Opponent bench players are never shown.
    all_rows = [r for g in data["games"] for k in ("my_starters", "my_bench", "opponents") for r in g[k]]
    assert not any(r["name"] == "Drake London" for r in all_rows)

    # Unmapped provider player is surfaced, not hidden.
    unmapped = [r for r in data["no_game"]["my_bench"] if not r["mapped"]]
    assert [r["name"] for r in unmapped] == ["Zzyzx Placeholder"]

    # Name-only players (no yahoo_id in the catalog) resolved by exact name+team+position.
    assert any(r["name"] == "Brock Bowers" for g in data["games"] for r in g["my_starters"])


def test_matchups_use_provider_totals(two_leagues: TestClient) -> None:
    resp = two_leagues.get("/api/matchups", params={"season": 2026, "week": 4}).json()
    cards = {c["league_name"]: c for c in resp["matchups"]}
    a = cards["Sunday Funday"]
    assert (a["my_team"]["name"], a["my_team"]["score"], a["my_team"]["projected"]) == ("Ankit's Aces", 112.34, 131.2)
    assert (a["opponent"]["name"], a["opponent"]["score"]) == ("Gridiron Gurus", 98.76)
    b = cards["Work League"]
    assert (b["my_team"]["name"], b["opponent"]["name"]) == ("Office Kings", "Spreadsheet Slayers")

    detail = two_leagues.get(f"/api/matchups/{a['id']}").json()
    assert len(detail["my_starters"]) == 9 and len(detail["opponent_starters"]) == 9
    assert {r["ownership"] for r in detail["opponent_starters"]} == {"OPPONENT"}
    assert detail["my_engine_total"] > 0


def test_custom_team_appears_with_imported_leagues(two_leagues: TestClient, db: Session) -> None:
    resp = two_leagues.post(
        "/api/manual-teams",
        json={
            "name": "Couch Team",
            "preset": "half_ppr",
            "players": [{"player_id": player_id(db, "Josh Allen"), "slot": "starter"}],
        },
    )
    assert resp.status_code == 200
    data = game_day(two_leagues)
    buf = find_game(data, "NE", "BUF")
    assert ("Josh Allen", "Couch Team") in rows(buf, "my_starters")
    assert data["team_count"] == 3
    cards = two_leagues.get("/api/matchups").json()["matchups"]
    couch = next(c for c in cards if c["provider"] == "manual")
    assert couch["has_matchup"] is False and couch["my_team"]["score"] == 19.52


def test_one_failing_league_does_not_break_the_page(two_leagues: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original = FixtureYahooClient.get

    def flaky(self: FixtureYahooClient, path: str) -> Any:
        if B in path:
            raise ProviderUnavailable()
        return original(self, path)

    monkeypatch.setattr(FixtureYahooClient, "get", flaky)
    data = game_day(two_leagues, refresh=True)
    assert [(e["league_name"], e["code"]) for e in data["league_errors"]] == [("Work League", "PROVIDER_UNAVAILABLE")]
    buf = find_game(data, "NE", "BUF")
    # League A refreshed fine; League B still shows its last-synced roster.
    assert ("Josh Allen", "Sunday Funday") in rows(buf, "my_starters")
    assert ("Josh Allen", "Work League") in rows(buf, "opponents")


def test_expired_refresh_token_surfaces_auth_expired(two_leagues: TestClient) -> None:
    assert two_leagues.post("/api/providers/yahoo/_fixture/expire").status_code == 200
    data = game_day(two_leagues)
    assert {e["code"] for e in data["league_errors"]} == {"PROVIDER_AUTH_EXPIRED"}
    assert len(data["league_errors"]) == 2
    assert "Reconnect Yahoo" in data["league_errors"][0]["message"]
    # Cached rosters keep rendering.
    assert find_game(data, "NE", "BUF")["my_starters"]

    resp = two_leagues.post("/api/providers/yahoo/discover")
    assert resp.status_code == 401 and resp.json()["code"] == "PROVIDER_AUTH_EXPIRED"

    # Reconnecting clears it.
    connect_yahoo_fixture(two_leagues)
    assert game_day(two_leagues, refresh=True)["league_errors"] == []


def test_live_data_unavailable_is_reported_inline(client: TestClient, db: Session) -> None:
    class Down:
        def get_state(self) -> NFLState:
            return NFLState(season=2026, week=4)

        def get_players(self) -> list[Any]:
            raise LiveDataUnavailable()

        def get_schedule(self, season: int, week: int) -> list[Any]:
            raise LiveDataUnavailable()

        def get_week_stats(self, season: int, week: int) -> list[Any]:
            raise LiveDataUnavailable()

    set_nfl_data_provider(Down())
    try:
        data = game_day(client)
    finally:
        set_nfl_data_provider(None)
    assert data["live_data_available"] is False
    assert data["league_errors"][0]["code"] == "LIVE_DATA_UNAVAILABLE"
    assert data["has_teams"] is False


def test_select_team_not_in_league_is_rejected(client: TestClient) -> None:
    connect_yahoo_fixture(client)
    imported = client.post("/api/leagues/import", json={"provider": "yahoo", "league_ids": [A, B]}).json()
    other_league_team = imported[1]["teams"][0]["id"]
    resp = client.post(f"/api/leagues/{imported[0]['league']['id']}/select-team", json={"team_id": other_league_team})
    assert resp.status_code == 404
    # Unselected league shows TEAM_NOT_SELECTED inline.
    data = game_day(client)
    assert {e["code"] for e in data["league_errors"]} == {"TEAM_NOT_SELECTED"}


def test_import_unknown_league(client: TestClient) -> None:
    connect_yahoo_fixture(client)
    resp = client.post("/api/leagues/import", json={"provider": "yahoo", "league_ids": ["461.l.9999"]})
    assert resp.status_code == 404 and resp.json()["code"] == "LEAGUE_NOT_FOUND"


def test_discover_requires_connection(client: TestClient) -> None:
    resp = client.post("/api/providers/yahoo/discover")
    assert resp.status_code == 401 and resp.json()["code"] == "PROVIDER_AUTH_REQUIRED"


def test_delete_league(two_leagues: TestClient) -> None:
    league_id = two_leagues.get("/api/leagues").json()[0]["id"]
    assert two_leagues.delete(f"/api/leagues/{league_id}").status_code == 200
    assert [lg["name"] for lg in two_leagues.get("/api/leagues").json()] == ["Work League"]
    buf = find_game(game_day(two_leagues), "NE", "BUF")
    assert ("Josh Allen", "Sunday Funday") not in rows(buf, "my_starters")
