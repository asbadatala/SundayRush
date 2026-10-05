"""Yahoo NFL stat_id -> normalized stat key, and league settings -> NormalizedScoringRules."""

from typing import Any

from app.domain.normalized import NormalizedScoringRules
from app.logging import log

YAHOO_STAT_ID_TO_NORMALIZED: dict[int, str] = {
    1: "pass_att",
    2: "pass_cmp",
    3: "pass_inc",
    4: "pass_yards",
    5: "pass_td",
    6: "interception",
    7: "pass_sack",
    8: "rush_att",
    9: "rush_yards",
    10: "rush_td",
    11: "reception",
    12: "receiving_yards",
    13: "receiving_td",
    14: "return_yards",
    15: "return_td",
    16: "two_pt",
    17: "fumble",
    18: "fumble_lost",
    57: "fumble_rec_td",
    78: "target",
}

# Kicker (19-30) and team defense (31-56, 58+ excluding offense) categories: scoring deferred.
_DEFERRED_POSITION_TYPES = {"K", "DT", "DP"}


def to_scoring_rules(categories: list[dict[str, Any]], modifiers: list[dict[str, Any]]) -> NormalizedScoringRules:
    position_type = {int(c["stat_id"]): c.get("position_type") for c in categories if "stat_id" in c}
    names = {int(c["stat_id"]): c.get("display_name") or c.get("name") for c in categories if "stat_id" in c}
    rules: dict[str, float] = {}
    unsupported: list[dict[str, Any]] = []
    for m in modifiers:
        stat_id = int(m["stat_id"])
        value = float(m.get("value") or 0)
        key = YAHOO_STAT_ID_TO_NORMALIZED.get(stat_id)
        entry = {"stat_id": stat_id, "name": names.get(stat_id), "value": value}
        if m.get("bonuses"):
            unsupported.append({**entry, "reason": "bonus"})
        if key is None:
            reason = "deferred" if position_type.get(stat_id) in _DEFERRED_POSITION_TYPES else "unmapped"
            unsupported.append({**entry, "reason": reason})
            if reason == "unmapped":
                log.warning("yahoo_stat_unmapped", stat_id=stat_id, name=names.get(stat_id))
            continue
        rules[key] = rules.get(key, 0.0) + value
    return NormalizedScoringRules(rules=rules, unsupported=unsupported)
