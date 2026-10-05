from app.providers.yahoo import parse
from app.providers.yahoo.client import fixture_name
from app.providers.yahoo.stat_map import to_scoring_rules
from tests.conftest import load_fixture

A = "461.l.1001"


def y(path: str) -> dict:  # type: ignore[type-arg]
    return load_fixture("yahoo", fixture_name(path))  # type: ignore[no-any-return]


def test_flatten_and_counted() -> None:
    assert parse.flatten([{"a": 1}, [], [{"b": 2}, {"c": 3}]]) == {"a": 1, "b": 2, "c": 3}
    assert parse.counted({"1": {"x": "b"}, "0": {"x": "a"}, "count": 2}, "x") == ["a", "b"]
    assert parse.counted([], "x") == []


def test_parse_leagues() -> None:
    leagues = parse.parse_leagues(y("users;use_login=1/games;game_keys=nfl/leagues"))
    assert [(lg.external_league_id, lg.name, lg.season, lg.num_teams) for lg in leagues] == [
        ("461.l.1001", "Sunday Funday", 2026, 4),
        ("461.l.2002", "Work League", 2026, 4),
    ]


def test_parse_teams_detects_owned_team() -> None:
    teams = parse.parse_teams(y(f"league/{A}/teams"))
    assert len(teams) == 4
    owned = [t for t in teams if t.is_owned_by_current_user]
    assert [t.name for t in owned] == ["Ankit's Aces"]
    assert owned[0].external_team_id == f"{A}.t.1"


def test_parse_roster_splits_starters_bench_ir() -> None:
    roster = parse.parse_roster(y(f"team/{A}.t.1/roster;week=4"), 4)
    by_name = {p.full_name: p for p in roster.players}
    allen = by_name["Josh Allen"]
    assert (allen.provider_player_id, allen.position, allen.nfl_team, allen.slot) == ("30977", "QB", "Buf", "QB")
    assert allen.is_starter and not allen.is_bench
    flex = by_name["Puka Nacua"]
    assert flex.slot == "W/R/T" and flex.is_starter
    bench = by_name["Justin Jefferson"]
    assert bench.is_bench and not bench.is_starter and bench.status == "Q"
    ir = by_name["Breece Hall"]
    assert ir.is_ir and ir.is_bench and not ir.is_starter
    assert by_name["Buffalo"].position == "DEF"
    assert sum(p.is_starter for p in roster.players) == 9


def test_parse_scoreboard_points_and_projections() -> None:
    matchups = parse.parse_scoreboard(y(f"league/{A}/scoreboard;week=4"), 4)
    assert len(matchups) == 2
    first = matchups[0]
    assert first.week == 4 and first.status == "midevent"
    assert [(s.external_team_id, s.points, s.projected_points) for s in first.teams] == [
        (f"{A}.t.1", 112.34, 131.2),
        (f"{A}.t.2", 98.76, 120.4),
    ]


def test_settings_to_scoring_rules() -> None:
    categories, modifiers = parse.parse_settings(y(f"league/{A}/settings"))
    rules = to_scoring_rules(categories, modifiers)
    assert rules.rules["pass_yards"] == 0.04
    assert rules.rules["pass_td"] == 4
    assert rules.rules["interception"] == -1
    assert rules.rules["reception"] == 1
    assert rules.rules["fumble_lost"] == -2
    # Kicker/defense stat_ids are recorded as deferred, not silently dropped.
    deferred = {u["stat_id"] for u in rules.unsupported if u["reason"] == "deferred"}
    assert {19, 29, 32, 33} <= deferred


def test_unmapped_and_bonus_stats_are_reported() -> None:
    rules = to_scoring_rules(
        [{"stat_id": 999, "name": "Mystery", "position_type": "O"}],
        [{"stat_id": 999, "value": "1"}, {"stat_id": 4, "value": "0.05", "bonuses": [{"bonus": {"target": 300}}]}],
    )
    assert rules.rules == {"pass_yards": 0.05}
    assert {(u["stat_id"], u["reason"]) for u in rules.unsupported} == {(999, "unmapped"), (4, "bonus")}
