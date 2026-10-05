"""NFL team code normalization. Canonical codes follow Sleeper (e.g. WAS, LAR, JAX)."""

CANONICAL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
    "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}  # fmt: skip

_ALIASES = {
    "WSH": "WAS",
    "LA": "LAR",
    "JAC": "JAX",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
    "GNB": "GB",
    "KAN": "KC",
    "NWE": "NE",
    "NOR": "NO",
    "SFO": "SF",
    "TAM": "TB",
}


def normalize_team(code: str | None) -> str | None:
    if not code:
        return None
    upper = code.strip().upper()
    if upper in ("FA", "FREE AGENT", ""):
        return None
    return _ALIASES.get(upper, upper)
