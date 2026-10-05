"""Real YahooOAuth + YahooClient code paths, with Yahoo's HTTP endpoints mocked by respx."""

from collections.abc import Iterator
from datetime import timedelta
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import get_settings
from app.crypto import decrypt
from app.domain.models import ProviderConnection, utcnow
from app.providers.yahoo.client import BASE_URL, fixture_name
from app.providers.yahoo.oauth import AUTH_URL, TOKEN_URL, set_oauth_client
from tests.conftest import FIXTURES


@pytest.fixture
def real_yahoo(monkeypatch: pytest.MonkeyPatch) -> Iterator[respx.MockRouter]:
    settings = get_settings()
    monkeypatch.setattr(settings, "fixture_mode", False)
    monkeypatch.setattr(settings, "yahoo_client_id", "cid")
    monkeypatch.setattr(settings, "yahoo_client_secret", "secret")
    set_oauth_client(None)

    def serve_fixture(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.raw_path.decode().split("?")[0]).removeprefix("/fantasy/v2/")
        file = FIXTURES / "yahoo" / fixture_name(path)
        if not file.exists():
            return httpx.Response(404)
        return httpx.Response(200, content=file.read_bytes(), headers={"content-type": "application/json"})

    with respx.mock(assert_all_called=False) as router:
        router.route(host="testserver").pass_through()
        router.get(url__startswith=BASE_URL).mock(side_effect=serve_fixture)
        yield router
    set_oauth_client(None)


def _connect(client: TestClient, router: respx.MockRouter) -> respx.Route:
    start = client.get("/api/providers/yahoo/auth/start", follow_redirects=False)
    assert start.status_code == 302
    location = start.headers["location"]
    assert location.startswith(AUTH_URL)
    params = parse_qs(urlparse(location).query)
    assert params["scope"] == ["fspt-r"] and params["response_type"] == ["code"]
    state = params["state"][0]

    token = router.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "AT-1",
                "refresh_token": "RT-1",
                "expires_in": 3600,
                "xoauth_yahoo_guid": "GUID",
            },
        )
    )
    done = client.get(f"/api/providers/yahoo/auth/callback?code=abc&state={state}", follow_redirects=False)
    assert done.status_code == 302 and done.headers["location"] == "/teams/yahoo/select"
    body = parse_qs(token.calls.last.request.content.decode())
    assert body["grant_type"] == ["authorization_code"] and body["code"] == ["abc"]
    assert token.calls.last.request.headers["authorization"].startswith("Basic ")
    return token


def test_connect_stores_encrypted_tokens(client: TestClient, db: Session, real_yahoo: respx.MockRouter) -> None:
    _connect(client, real_yahoo)
    conn = db.exec(select(ProviderConnection)).one()
    assert conn.encrypted_access_token and "AT-1" not in conn.encrypted_access_token
    assert decrypt(conn.encrypted_access_token) == "AT-1"
    assert decrypt(conn.encrypted_refresh_token or "") == "RT-1"
    assert conn.scopes == "fspt-r" and conn.external_account_identifier == "GUID"
    providers = {p["id"]: p for p in client.get("/api/providers").json()}
    assert providers["yahoo"]["connected"] is True
    assert providers["sleeper"]["available"] is False


def test_callback_rejects_bad_state(client: TestClient, real_yahoo: respx.MockRouter) -> None:
    client.get("/api/providers/yahoo/auth/start", follow_redirects=False)
    resp = client.get("/api/providers/yahoo/auth/callback?code=abc&state=forged", follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "/teams/new?error=OAUTH_STATE_INVALID"


def test_token_refresh_before_expiry_then_discover(
    client: TestClient, db: Session, real_yahoo: respx.MockRouter
) -> None:
    _connect(client, real_yahoo)
    conn = db.exec(select(ProviderConnection)).one()
    conn.token_expires_at = utcnow() + timedelta(minutes=2)  # inside the 5-minute refresh window
    db.add(conn)
    db.commit()

    refresh = real_yahoo.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "AT-2", "expires_in": 3600})
    )
    resp = client.post("/api/providers/yahoo/discover")
    assert resp.status_code == 200, resp.text
    assert [lg["name"] for lg in resp.json()] == ["Sunday Funday", "Work League"]
    body = parse_qs(refresh.calls.last.request.content.decode())
    assert body["grant_type"] == ["refresh_token"] and body["refresh_token"] == ["RT-1"]
    api_call = next(c for c in real_yahoo.calls if c.request.url.host == "fantasysports.yahooapis.com")
    assert api_call.request.headers["authorization"] == "Bearer AT-2"
    assert api_call.request.url.params["format"] == "json"
    db.refresh(conn)
    assert decrypt(conn.encrypted_access_token or "") == "AT-2"
    assert decrypt(conn.encrypted_refresh_token or "") == "RT-1"  # Yahoo omitted it; keep the old one


def test_revoked_refresh_token_returns_auth_expired(
    client: TestClient, db: Session, real_yahoo: respx.MockRouter
) -> None:
    _connect(client, real_yahoo)
    conn = db.exec(select(ProviderConnection)).one()
    conn.token_expires_at = utcnow() - timedelta(minutes=1)
    db.add(conn)
    db.commit()
    real_yahoo.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    resp = client.post("/api/providers/yahoo/discover")
    assert resp.status_code == 401 and resp.json()["code"] == "PROVIDER_AUTH_EXPIRED"


def test_disconnect_deletes_tokens(client: TestClient, db: Session, real_yahoo: respx.MockRouter) -> None:
    _connect(client, real_yahoo)
    assert client.delete("/api/providers/yahoo/connection").json() == {"deleted": True}
    assert db.exec(select(ProviderConnection)).first() is None
