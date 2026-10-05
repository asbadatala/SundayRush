"""Pure, deterministic fantasy scoring (spec §14).

Points = sum(stats[key] * rules[key]) over normalized keys. Normalized stat keys are
canonical and non-overlapping, so no stat is ever counted twice.
"""

from collections.abc import Mapping

from app.domain.normalized import NormalizedScoringRules

# K/DEF scoring is deferred; their rows render "points unavailable" rather than a wrong number.
UNSCORED_POSITIONS = {"K", "DEF"}


def calculate_fantasy_points(stats: Mapping[str, float], rules: NormalizedScoringRules | Mapping[str, float]) -> float:
    weights = rules.rules if isinstance(rules, NormalizedScoringRules) else rules
    total = 0.0
    for key, per_unit in weights.items():
        value = stats.get(key)
        if value:
            total += float(value) * float(per_unit)
    return round(total + 0.0, 2)  # + 0.0 normalizes -0.0


def points_for_position(
    position: str, stats: Mapping[str, float] | None, rules: NormalizedScoringRules | Mapping[str, float]
) -> float | None:
    """None means 'points unavailable' for this position."""
    if position.upper() in UNSCORED_POSITIONS:
        return None
    return calculate_fantasy_points(stats or {}, rules)
