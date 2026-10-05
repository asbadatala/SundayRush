import pytest

from app.domain.normalized import GameStatus
from app.nfl_data.espn_schedule import map_status, parse_scoreboard
from app.nfl_data.sleeper_players import parse_players, parse_state
from app.nfl_data.sleeper_stats import parse_week_stats
from app.nfl_data.stat_keys import normalize_sleeper_stats
from app.nfl_data.teams import normalize_team
from tests.conftest import load_fixture


@pytest.mark.parametrize(
    ("name", "state", "expected"),
    [
        ("STATUS_SCHEDULED", "pre", GameStatus.SCHEDULED),
        ("STATUS_IN_PROGRESS", "in", GameStatus.LIVE),
        ("STATUS_END_PERIOD", "in", GameStatus.LIVE),
        ("STATUS_HALFTIME", "in", GameStatus.HALFTIME),
        ("STATUS_FINAL", "post", GameStatus.FINAL),
        ("STATUS_FINAL_OVERTIME", "post", GameStatus.FINAL),
        ("STATUS_POSTPONED", "post", GameStatus.POSTPONED),
        ("STATUS_CANCELED", "post", GameStatus.CANCELED),
        ("STATUS_SOMETHING_NEW", "in", GameStatus.LIVE),
        ("STATUS_SOMETHING_NEW", "pre", GameStatus.SCHEDULED),
    ],
)
def test_espn_status_mapping(name: str, state: str, expected: GameStatus) -> None:
    assert map_status({"name": name, "state": state}) == expected


def test_parse_recorded_scoreboard() -> None:
    games = parse_scoreboard(load_fixture("nfl", "espn_scoreboard_2026_4.json"), 2026, 4)
    assert len(games) == 16
    by_matchup = {f"{g.away_team}@{g.home_team}": g for g in games}
    # ESPN WSH normalizes to canonical WAS
    assert "IND@WAS" in by_matchup or "WAS@IND" in by_matchup
    final = by_matchup["NE@BUF"]
    assert final.status == GameStatus.FINAL and final.home_score == 26 and final.away_score == 29
    assert final.broadcaster == "CBS" and final.clock is None
    scheduled = by_matchup["DET@CAR"]
    assert scheduled.status == GameStatus.SCHEDULED and scheduled.home_score is None
    live = [g for g in games if g.status in (GameStatus.LIVE, GameStatus.HALFTIME)]
    assert live and all(g.quarter for g in live)


def test_team_normalization() -> None:
    assert normalize_team("WSH") == "WAS"
    assert normalize_team("Buf") == "BUF"
    assert normalize_team("jax") == "JAX"
    assert normalize_team("FA") is None
    assert normalize_team(None) is None


def test_sleeper_stat_normalization_sums_and_renames() -> None:
    out = normalize_sleeper_stats(
        {"pass_yd": 268, "pass_int": 1, "rec": 3, "pass_2pt": 1, "rush_2pt": 1, "kr_td": 1, "pr_td": 1, "pts_ppr": 99}
    )
    assert out == {"pass_yards": 268, "interception": 1, "reception": 3, "two_pt": 2, "return_td": 2}


def test_parse_players_filters_positions_and_defenses() -> None:
    players = parse_players(
        {
            "4984": {
                "player_id": "4984",
                "full_name": "Josh Allen",
                "position": "QB",
                "team": "BUF",
                "yahoo_id": 30977,
            },
            "BUF": {
                "player_id": "BUF",
                "first_name": "Buffalo",
                "last_name": "Bills",
                "position": "DEF",
                "team": "BUF",
            },
            "1": {"player_id": "1", "full_name": "Some Lineman", "position": "OT", "team": "BUF"},
        }
    )
    assert {p.full_name for p in players} == {"Josh Allen", "Buffalo Bills"}
    allen = next(p for p in players if p.position == "QB")
    assert allen.yahoo_id == "30977"


def test_parse_state_and_stats_fixtures() -> None:
    state = parse_state(load_fixture("nfl", "sleeper_state.json"))
    assert (state.season, state.week) == (2026, 4)
    stats = parse_week_stats(load_fixture("nfl", "sleeper_stats_2026_4.json"))
    allen = next(s for s in stats if s.sleeper_id == "4984")
    assert allen.nfl_team == "BUF" and allen.stats["pass_yards"] == 253
