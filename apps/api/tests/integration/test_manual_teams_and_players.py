from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.domain.models import CanonicalPlayer, PlayerIdMapping
from app.main import app
from app.player_resolution.resolver import PlayerRef, PlayerResolver
from tests.conftest import player_id
from tests.integration.helpers import find_game, game_day


def test_session_cookie_is_http_only_and_persistent(client: TestClient) -> None:
    resp = client.get("/api/session")
    cookie = resp.headers["set-cookie"]
    assert "ff_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=" in cookie
    # Same cookie -> no new session minted.
    assert "set-cookie" not in client.get("/api/session").headers


def test_player_search(client: TestClient) -> None:
    results = client.get("/api/players/search", params={"q": "jamarr"}).json()
    assert results[0]["full_name"] == "Ja'Marr Chase"
    results = client.get("/api/players/search", params={"q": "josh all"}).json()
    assert results[0]["full_name"] == "Josh Allen" and results[0]["position"] == "QB"
    bills = client.get("/api/players/search", params={"q": "bills", "position": "DEF"}).json()
    assert bills[0]["full_name"] == "Buffalo Bills"
    assert client.get("/api/players/search", params={"q": "j"}).status_code == 422
    pid = results[0]["id"]
    assert client.get(f"/api/players/{pid}").json()["nfl_team"] == "BUF"
    assert client.get("/api/players/999999").status_code == 404


def test_manual_team_crud_and_game_day(client: TestClient, db: Session) -> None:
    allen, chase, jefferson = (player_id(db, n) for n in ("Josh Allen", "Ja'Marr Chase", "Justin Jefferson"))
    created = client.post(
        "/api/manual-teams",
        json={"name": "My Team", "preset": "ppr", "players": [{"player_id": allen, "slot": "starter"}]},
    )
    assert created.status_code == 200
    team = created.json()
    assert team["scoring_name"] == "Full PPR" and [p["player"]["full_name"] for p in team["starters"]] == ["Josh Allen"]

    client.post(f"/api/manual-teams/{team['id']}/players", json={"player_id": chase, "slot": "starter"})
    team = client.post(f"/api/manual-teams/{team['id']}/players", json={"player_id": jefferson, "slot": "bench"}).json()
    assert [p["player"]["full_name"] for p in team["bench"]] == ["Justin Jefferson"]
    # Moving a player re-slots rather than duplicating.
    team = client.post(f"/api/manual-teams/{team['id']}/players", json={"player_id": chase, "slot": "bench"}).json()
    assert len(team["starters"]) == 1 and len(team["bench"]) == 2

    team = client.patch(f"/api/manual-teams/{team['id']}", json={"name": "Renamed", "preset": "standard"}).json()
    assert (team["name"], team["preset"]) == ("Renamed", "standard")

    data = game_day(client)
    assert data["has_teams"] and data["team_count"] == 1 and data["league_errors"] == []
    buf = find_game(data, "NE", "BUF")
    assert [(r["name"], r["league_name"], r["provider"]) for r in buf["my_starters"]] == [
        ("Josh Allen", "Renamed", "manual")
    ]
    cin = find_game(data, "JAX", "CIN")
    assert [r["name"] for r in cin["my_bench"]] == ["Ja'Marr Chase"]

    team = client.delete(f"/api/manual-teams/{team['id']}/players/{chase}").json()
    assert len(team["bench"]) == 1
    assert client.delete(f"/api/manual-teams/{team['id']}").json() == {"deleted": True}
    assert client.get("/api/manual-teams").json() == []
    assert game_day(client)["has_teams"] is False


def test_users_cannot_see_each_others_teams(client: TestClient, db: Session) -> None:
    team = client.post("/api/manual-teams", json={"name": "Mine", "preset": "ppr"}).json()
    with TestClient(app, base_url="http://testserver") as other:
        assert other.get("/api/manual-teams").json() == []
        assert other.get(f"/api/manual-teams/{team['id']}").status_code == 404
        assert other.delete(f"/api/manual-teams/{team['id']}").status_code == 404
    assert len(client.get("/api/manual-teams").json()) == 1


def test_invalid_manual_team_input(client: TestClient) -> None:
    assert client.post("/api/manual-teams", json={"name": "", "preset": "ppr"}).json()["code"] == "VALIDATION_FAILED"
    assert client.post("/api/manual-teams", json={"name": "X", "preset": "superflex"}).status_code == 422


def test_clear_session_deletes_everything(client: TestClient) -> None:
    client.post("/api/manual-teams", json={"name": "Mine", "preset": "ppr"})
    assert client.delete("/api/session").json() == {"deleted": True}
    assert client.get("/api/manual-teams").json() == []


def test_resolver_priority(db: Session) -> None:
    resolver = PlayerResolver(db)
    allen = player_id(db, "Josh Allen")
    bowers = player_id(db, "Brock Bowers")

    # 2. canonical yahoo_id
    r = resolver.resolve(PlayerRef("yahoo", "30977", "J. Allen", "QB", "Buf"))
    assert (r.player_id, r.method) == (allen, "provider_id")
    # 1. mapping table now short-circuits everything else
    r = resolver.resolve(PlayerRef("yahoo", "30977", "Totally Different", "WR", "NYJ"))
    assert (r.player_id, r.method) == (allen, "mapping")
    # 3. exact normalized name + team + position
    r = resolver.resolve(PlayerRef("yahoo", "55555", "Brock Bowers", "TE", "LV"))
    assert (r.player_id, r.method) == (bowers, "exact")
    # 4. fuzzy (typo) above threshold
    r = resolver.resolve(PlayerRef("yahoo", "55556", "Brock Bowerss", "TE", "LV"))
    assert (r.player_id, r.method) == (bowers, "fuzzy") and r.confidence >= 0.92
    # below threshold -> unresolved, not saved
    r = resolver.resolve(PlayerRef("yahoo", "55557", "Bob Smith", "TE", "LV"))
    assert r.player_id is None
    db.commit()
    saved = {m.external_id: m.method for m in db.exec(select(PlayerIdMapping))}
    assert saved == {"30977": "provider_id", "55555": "exact", "55556": "fuzzy"}
    # Defenses resolve by team.
    r = resolver.resolve(PlayerRef("yahoo", "100002", "Buffalo", "DEF", "Buf"))
    defense = db.get(CanonicalPlayer, r.player_id)
    assert defense is not None and defense.full_name == "Buffalo Bills"


def test_player_sync_invalidates_cached_weeks(db: Session) -> None:
    """A week loaded before the catalog existed must re-join stats once players arrive."""
    from app.cache.db_cache import DbCache
    from app.nfl_data.composite import FixtureNFLDataProvider
    from app.nfl_data.sync import sync_players
    from tests.conftest import FIXTURES

    cache = DbCache(db)
    cache.set("nfl:week:2026:4", "2026-10-04T00:00:00+00:00", 3600)
    sync_players(db, FixtureNFLDataProvider(FIXTURES))
    assert cache.get("nfl:week:2026:4") is None
