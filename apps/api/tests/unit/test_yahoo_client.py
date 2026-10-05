import httpx
import pytest
import respx

from app.errors import LeagueNotFound, ProviderAuthExpired, ProviderRateLimited, ProviderUnavailable
from app.player_resolution.names import normalize_name
from app.player_resolution.resolver import FUZZY_THRESHOLD, best_fuzzy
from app.providers.yahoo.client import BASE_URL, YahooClient


def make_client(tokens: list[str]) -> tuple[YahooClient, list[bool]]:
    calls: list[bool] = []

    def get_token(force: bool) -> str:
        calls.append(force)
        return tokens[min(len(calls) - 1, len(tokens) - 1)]

    return YahooClient(get_token, http=httpx.Client(base_url=BASE_URL), sleep=lambda _: None), calls


@respx.mock
def test_retries_on_999_then_succeeds() -> None:
    route = respx.get(f"{BASE_URL}league/x").mock(
        side_effect=[httpx.Response(999), httpx.Response(429), httpx.Response(200, json={"ok": 1})]
    )
    client, _ = make_client(["t"])
    assert client.get("league/x") == {"ok": 1}
    assert route.call_count == 3
    assert route.calls.last.request.url.params["format"] == "json"


@respx.mock
def test_rate_limit_exhausted_raises() -> None:
    respx.get(f"{BASE_URL}league/x").mock(return_value=httpx.Response(999))
    client, _ = make_client(["t"])
    with pytest.raises(ProviderRateLimited):
        client.get("league/x")


@respx.mock
def test_401_forces_one_refresh_then_retries() -> None:
    route = respx.get(f"{BASE_URL}league/x").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"ok": 2})]
    )
    client, calls = make_client(["old", "new"])
    assert client.get("league/x") == {"ok": 2}
    assert calls == [False, True]
    assert route.calls.last.request.headers["Authorization"] == "Bearer new"


@respx.mock
def test_second_401_is_auth_expired_and_404_is_not_found() -> None:
    respx.get(f"{BASE_URL}league/x").mock(return_value=httpx.Response(401))
    respx.get(f"{BASE_URL}league/y").mock(return_value=httpx.Response(404))
    client, _ = make_client(["t"])
    with pytest.raises(ProviderAuthExpired):
        client.get("league/x")
    with pytest.raises(LeagueNotFound):
        client.get("league/y")


def test_normalize_name() -> None:
    assert normalize_name("D.J. Moore Jr.") == "dj moore"
    assert normalize_name("Ja'Marr Chase") == "jamarr chase"
    assert normalize_name("Amon-Ra St. Brown") == "amon ra st brown"
    assert normalize_name("Marvin Harrison  II") == "marvin harrison"


def test_fuzzy_threshold() -> None:
    candidates = {1: "kenneth walker", 2: "kenneth gainwell", 3: "kendrick bourne"}
    pid, score = best_fuzzy("Kenneth Walker III", candidates) or (0, 0)
    assert pid == 1 and score >= FUZZY_THRESHOLD
    # A typo-level difference clears the bar; a different player never does.
    _, typo = best_fuzzy("Keneth Walker", candidates) or (0, 0)
    assert typo >= FUZZY_THRESHOLD
    _, other = best_fuzzy("Kenneth Gaines", {1: "kenneth walker"}) or (0, 0)
    assert other < FUZZY_THRESHOLD


@respx.mock
def test_403_explains_missing_app_permission() -> None:
    respx.get(f"{BASE_URL}game/nfl").mock(
        return_value=httpx.Response(
            403, json={"error": {"description": "This application is not authorized to perform this action."}}
        )
    )
    client, _ = make_client(["t"])
    with pytest.raises(ProviderUnavailable, match="Fantasy Sports"):
        client.get("game/nfl")
