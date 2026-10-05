from app.game_day.ownership import Ownership
from app.game_day.schemas import GameGroup, GameOut, NoGameGroup, PlayerRow

_POSITION_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DEF": 5}
# live first, then upcoming by kickoff, then final; postponed/canceled last
_STATUS_RANK = {
    "live": 0,
    "halftime": 0,
    "pregame": 1,
    "scheduled": 1,
    "final": 2,
    "postponed": 3,
    "canceled": 3,
}


def game_sort_key(game: GameOut) -> tuple[int, float, str]:
    return (_STATUS_RANK.get(game.status, 3), game.kickoff_at.timestamp(), game.external_game_id)


def sort_games(games: list[GameOut]) -> list[GameOut]:
    return sorted(games, key=game_sort_key)


def row_sort_key(row: PlayerRow) -> tuple[int, str, str]:
    return (_POSITION_ORDER.get(row.position, 9), row.name, row.league_name)


def _split(rows: list[PlayerRow]) -> tuple[list[PlayerRow], list[PlayerRow], list[PlayerRow]]:
    rows = sorted(rows, key=row_sort_key)
    return (
        [r for r in rows if r.ownership == Ownership.MY_STARTER],
        [r for r in rows if r.ownership == Ownership.MY_BENCH],
        [r for r in rows if r.ownership == Ownership.OPPONENT],
    )


def group_rows(rows: list[PlayerRow], games: list[GameOut]) -> tuple[list[GameGroup], NoGameGroup]:
    """Bucket rows under their NFL game. Every game is returned (the client filters to
    relevant ones unless 'All NFL games' is on); rows without a game go to NoGameGroup."""
    by_game: dict[int, list[PlayerRow]] = {g.id: [] for g in games}
    no_game: list[PlayerRow] = []
    for row in rows:
        if row.game_id is not None and row.game_id in by_game:
            by_game[row.game_id].append(row)
        else:
            no_game.append(row)
    groups = []
    for game in sort_games(games):
        starters, bench, opponents = _split(by_game[game.id])
        groups.append(GameGroup(game=game, my_starters=starters, my_bench=bench, opponents=opponents))
    starters, bench, opponents = _split(no_game)
    return groups, NoGameGroup(my_starters=starters, my_bench=bench, opponents=opponents)
