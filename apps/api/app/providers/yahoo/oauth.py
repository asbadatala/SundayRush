"""Yahoo OAuth 2.0 (authorization code flow, read-only `fspt-r` scope). Server-side only."""

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Protocol
from urllib.parse import urlencode

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.crypto import decrypt, encrypt
from app.domain.models import ProviderConnection, User, utcnow
from app.errors import ProviderAuthExpired, ProviderAuthRequired, ProviderUnavailable
from app.logging import log

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
SCOPE = "fspt-r"
PROVIDER = "yahoo"
REFRESH_SKEW = timedelta(minutes=5)


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    expires_in: int
    guid: str | None = None


class OAuthClient(Protocol):
    def authorize_url(self, state: str) -> str: ...

    def exchange_code(self, code: str) -> TokenSet: ...

    def refresh(self, refresh_token: str) -> TokenSet: ...


def _token_set(payload: dict[str, object], fallback_refresh: str | None = None) -> TokenSet:
    return TokenSet(
        access_token=str(payload["access_token"]),
        refresh_token=str(payload.get("refresh_token") or fallback_refresh or ""),
        expires_in=int(str(payload.get("expires_in") or 3600)),
        guid=str(payload["xoauth_yahoo_guid"]) if payload.get("xoauth_yahoo_guid") else None,
    )


class YahooOAuth:
    def __init__(self, http: httpx.Client | None = None):
        self.settings = get_settings()
        self.http = http or httpx.Client(timeout=15.0)

    def authorize_url(self, state: str) -> str:
        if not self.settings.yahoo_client_id:
            raise ProviderUnavailable("Yahoo isn't configured on this server yet (missing YAHOO_CLIENT_ID).")
        params = {
            "client_id": self.settings.yahoo_client_id,
            "redirect_uri": self.settings.yahoo_redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def _post(self, data: dict[str, str]) -> dict[str, object]:
        try:
            resp = self.http.post(
                TOKEN_URL,
                data={**data, "redirect_uri": self.settings.yahoo_redirect_uri},
                auth=(self.settings.yahoo_client_id, self.settings.yahoo_client_secret),
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable() from exc
        if resp.status_code in (400, 401):
            log.warning("yahoo_token_rejected", status=resp.status_code, grant=data.get("grant_type"))
            raise ProviderAuthExpired()
        if resp.status_code >= 400:
            raise ProviderUnavailable()
        return resp.json()  # type: ignore[no-any-return]

    def exchange_code(self, code: str) -> TokenSet:
        return _token_set(self._post({"grant_type": "authorization_code", "code": code}))

    def refresh(self, refresh_token: str) -> TokenSet:
        payload = self._post({"grant_type": "refresh_token", "refresh_token": refresh_token})
        return _token_set(payload, fallback_refresh=refresh_token)


class FakeYahooOAuth:
    """FIXTURE_MODE: skips Yahoo entirely. A refresh token of 'revoked' simulates revocation."""

    REVOKED = "revoked"

    def authorize_url(self, state: str) -> str:
        return f"/api/providers/yahoo/auth/callback?{urlencode({'code': 'fixture-code', 'state': state})}"

    def exchange_code(self, code: str) -> TokenSet:
        return TokenSet("fixture-access", "fixture-refresh", 3600, guid="FIXTUREGUID")

    def refresh(self, refresh_token: str) -> TokenSet:
        if refresh_token == self.REVOKED:
            raise ProviderAuthExpired()
        return TokenSet("fixture-access-refreshed", refresh_token, 3600, guid="FIXTUREGUID")


_override: OAuthClient | None = None


def set_oauth_client(client: OAuthClient | None) -> None:
    global _override
    _override = client
    _default_oauth.cache_clear()


@lru_cache
def _default_oauth() -> OAuthClient:
    return FakeYahooOAuth() if get_settings().fixture_mode else YahooOAuth()


def get_oauth_client() -> OAuthClient:
    return _override or _default_oauth()


# --- connection storage ---------------------------------------------------------------


def get_connection(db: Session, user: User) -> ProviderConnection | None:
    return db.exec(
        select(ProviderConnection).where(ProviderConnection.user_id == user.id, ProviderConnection.provider == PROVIDER)
    ).first()


def store_tokens(db: Session, user: User, tokens: TokenSet) -> ProviderConnection:
    conn = get_connection(db, user) or ProviderConnection(user_id=user.id, provider=PROVIDER)
    conn.encrypted_access_token = encrypt(tokens.access_token)
    conn.encrypted_refresh_token = encrypt(tokens.refresh_token)
    conn.token_expires_at = utcnow() + timedelta(seconds=tokens.expires_in)
    conn.scopes = SCOPE
    if tokens.guid:
        conn.external_account_identifier = tokens.guid
    conn.updated_at = utcnow()
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def delete_connection(db: Session, user: User) -> bool:
    conn = get_connection(db, user)
    if conn is None:
        return False
    db.delete(conn)
    db.commit()
    return True


def ensure_fresh_token(db: Session, user: User, *, force: bool = False) -> str:
    """Return a valid access token, refreshing ~5 min before expiry (or when forced after a 401)."""
    conn = get_connection(db, user)
    if conn is None or not conn.encrypted_refresh_token:
        raise ProviderAuthRequired()
    access = decrypt(conn.encrypted_access_token) if conn.encrypted_access_token else None
    expires_at = conn.token_expires_at
    if not force and access and expires_at and expires_at - REFRESH_SKEW > utcnow():
        return access

    refresh_token = decrypt(conn.encrypted_refresh_token)
    if not refresh_token:
        raise ProviderAuthExpired()
    tokens = get_oauth_client().refresh(refresh_token)
    log.info("yahoo_token_refreshed", user_id=user.id)
    store_tokens(db, user, tokens)
    return tokens.access_token
