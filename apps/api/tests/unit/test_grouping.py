from datetime import UTC, datetime, timedelta

from app.game_day.grouping import group_rows, sort_games
from app.game_day.ownership import Ownership, classify
from app.game_day.schemas import GameOut, PlayerRow

T0 = datetime(2026, 10, 4, 17, 0, tzinfo=UTC)


def game(gid: int, status: str, kickoff: datetime, home: str = "H", away: str = "A") -> GameOut:
    return GameOut(
        id=gid,
        external_game_id=str(gid),
        kickoff_at=kickoff,
        home_team=f"{home}{gid}",
        away_team=f"{away}{gid}",
        home_score=None,
        away_score=None,
        status=status,
        status_detail=None,
        quarter=None,
        clock=None,
        broadcaster=None,
    )


def row(name: str, ownership: Ownership, league: str, game_id: int | None, position: str = "QB") -> PlayerRow:
    return PlayerRow(
        key=f"{league}:{name}",
        player_id=1,
        name=name,
        position=position,
        nfl_team="BUF",
        league_id=1,
        league_name=league,
        team_id=hash(league) % 1000,
        team_name=f"{league} team",
        provider="yahoo",
        ownership=ownership,
        slot=position,
        points=10.0,
        game_id=game_id,
    )


def test_classify() -> None:
    assert classify(is_user_team=True, is_starter=True) == Ownership.MY_STARTER
    assert classify(is_user_team=True, is_starter=False) == Ownership.MY_BENCH
    assert classify(is_user_team=False, is_starter=True) == Ownership.OPPONENT
    assert classify(is_user_team=False, is_starter=False) is None


def test_sort_live_then_upcoming_by_kickoff_then_final() -> None:
    games = [
        game(1, "final", T0),
        game(2, "scheduled", T0 + timedelta(hours=7)),
        game(3, "live", T0 + timedelta(hours=3)),
        game(4, "scheduled", T0 + timedelta(hours=4)),
        game(5, "halftime", T0 + timedelta(hours=3, minutes=20)),
        game(6, "postponed", T0),
        game(7, "final", T0 - timedelta(days=3)),
    ]
    assert [g.id for g in sort_games(games)] == [3, 5, 4, 2, 7, 1, 6]


def test_same_player_in_three_leagues_keeps_every_context() -> None:
    g = game(1, "live", T0)
    rows = [
        row("Josh Allen", Ownership.MY_STARTER, "League A", 1),
        row("Josh Allen", Ownership.OPPONENT, "League B", 1),
        row("Josh Allen", Ownership.MY_STARTER, "League C", 1),
        row("James Cook", Ownership.MY_BENCH, "League C", 1, "RB"),
    ]
    groups, no_game = group_rows(rows, [g])
    grp = groups[0]
    assert [(r.name, r.league_name) for r in grp.my_starters] == [
        ("Josh Allen", "League A"),
        ("Josh Allen", "League C"),
    ]
    assert [(r.name, r.league_name) for r in grp.opponents] == [("Josh Allen", "League B")]
    assert [r.name for r in grp.my_bench] == ["James Cook"]
    assert not (no_game.my_starters or no_game.my_bench or no_game.opponents)


def test_rows_without_game_go_to_no_game_group_and_irrelevant_games_kept() -> None:
    games = [game(1, "scheduled", T0), game(2, "final", T0)]
    rows = [row("Bye Guy", Ownership.MY_STARTER, "L", None), row("WR1", Ownership.MY_STARTER, "L", 2, "WR")]
    groups, no_game = group_rows(rows, games)
    assert [g.game.id for g in groups] == [1, 2]
    assert groups[0].my_starters == [] and [r.name for r in groups[1].my_starters] == ["WR1"]
    assert [r.name for r in no_game.my_starters] == ["Bye Guy"]


def test_rows_sorted_by_position_within_group() -> None:
    g = game(1, "live", T0)
    rows = [
        row("Tight End", Ownership.MY_STARTER, "L", 1, "TE"),
        row("Quarterback", Ownership.MY_STARTER, "L", 1, "QB"),
        row("Running Back", Ownership.MY_STARTER, "L", 1, "RB"),
    ]
    groups, _ = group_rows(rows, [g])
    assert [r.position for r in groups[0].my_starters] == ["QB", "RB", "TE"]
