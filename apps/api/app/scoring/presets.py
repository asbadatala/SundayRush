from app.domain.normalized import NormalizedScoringRules

# Matches Yahoo's default offensive scoring (INT -1, fumble lost -2).
_STANDARD: dict[str, float] = {
    "pass_yards": 0.04,
    "pass_td": 4,
    "interception": -1,
    "rush_yards": 0.1,
    "rush_td": 6,
    "reception": 0,
    "receiving_yards": 0.1,
    "receiving_td": 6,
    "return_td": 6,
    "two_pt": 2,
    "fumble_lost": -2,
    "fumble_rec_td": 6,
}

PRESETS: dict[str, dict[str, float]] = {
    "standard": _STANDARD,
    "half_ppr": {**_STANDARD, "reception": 0.5},
    "ppr": {**_STANDARD, "reception": 1},
}

PRESET_LABELS = {"standard": "Standard", "half_ppr": "Half PPR", "ppr": "Full PPR"}


def preset_rules(name: str) -> NormalizedScoringRules:
    if name not in PRESETS:
        raise KeyError(name)
    return NormalizedScoringRules(rules=dict(PRESETS[name]))
