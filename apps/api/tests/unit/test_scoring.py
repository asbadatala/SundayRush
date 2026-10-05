import pytest

from app.domain.normalized import NormalizedScoringRules
from app.scoring.engine import calculate_fantasy_points, points_for_position
from app.scoring.presets import PRESETS, preset_rules

STD = preset_rules("standard")
HALF = preset_rules("half_ppr")
PPR = preset_rules("ppr")


def test_passing_qb() -> None:
    stats = {"pass_yards": 300, "pass_td": 3, "interception": 1, "rush_yards": 20}
    # 12 + 12 - 1 + 2
    assert calculate_fantasy_points(stats, STD) == 25.0


def test_rushing_rb() -> None:
    stats = {"rush_yards": 112, "rush_td": 2, "rush_att": 22}
    assert calculate_fantasy_points(stats, STD) == 23.2


def test_receiving_wr() -> None:
    stats = {"reception": 8, "receiving_yards": 105, "receiving_td": 1, "target": 11}
    assert calculate_fantasy_points(stats, STD) == 16.5
    assert calculate_fantasy_points(stats, PPR) == 24.5


def test_ppr_vs_half_ppr_difference_is_half_point_per_catch() -> None:
    stats = {"reception": 7, "receiving_yards": 64}
    assert calculate_fantasy_points(stats, PPR) - calculate_fantasy_points(stats, HALF) == pytest.approx(3.5)
    assert calculate_fantasy_points(stats, HALF) - calculate_fantasy_points(stats, STD) == pytest.approx(3.5)


def test_turnovers_score_negative() -> None:
    stats = {"pass_yards": 50, "interception": 3, "fumble_lost": 2}
    # 2 - 3 - 4
    assert calculate_fantasy_points(stats, STD) == -5.0


def test_mixed_rushing_receiving_player_no_double_count() -> None:
    stats = {"rush_yards": 70, "rush_td": 1, "reception": 5, "receiving_yards": 45, "receiving_td": 1}
    # rush 7 + 6, rec 4.5 + 6 + 5 (ppr). Yards are counted once each, never as a combined total.
    assert calculate_fantasy_points(stats, PPR) == 28.5


def test_fractional_rules_and_rounding() -> None:
    rules = NormalizedScoringRules(rules={"pass_yards": 1 / 30, "reception": 0.25})
    assert calculate_fantasy_points({"pass_yards": 251, "reception": 3}, rules) == 9.12


def test_unknown_stats_and_missing_rules_are_ignored() -> None:
    assert calculate_fantasy_points({"tackles": 9, "rush_yards": 10}, {"rush_yards": 0.1}) == 1.0
    assert calculate_fantasy_points({}, STD) == 0.0


def test_deterministic_and_no_negative_zero() -> None:
    stats = {"interception": 0, "rush_yards": 0}
    assert str(calculate_fantasy_points(stats, STD)) == "0.0"


def test_k_and_def_points_unavailable() -> None:
    assert points_for_position("K", {"fg_made": 3}, STD) is None
    assert points_for_position("DEF", {"def_sack": 4}, STD) is None
    assert points_for_position("WR", None, STD) == 0.0


def test_presets_share_keys() -> None:
    assert set(PRESETS["standard"]) == set(PRESETS["ppr"]) == set(PRESETS["half_ppr"])
    assert (PRESETS["standard"]["reception"], PRESETS["half_ppr"]["reception"], PRESETS["ppr"]["reception"]) == (
        0,
        0.5,
        1,
    )
