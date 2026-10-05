from enum import StrEnum


class Ownership(StrEnum):
    MY_STARTER = "MY_STARTER"
    MY_BENCH = "MY_BENCH"
    OPPONENT = "OPPONENT"


def classify(*, is_user_team: bool, is_starter: bool) -> Ownership | None:
    """Ownership of one roster entry in one (league, team) context.

    Opponent bench players aren't relevant on game day (spec §10.7 uses the opponent's
    starting lineup), so they classify as None and are dropped.
    """
    if is_user_team:
        return Ownership.MY_STARTER if is_starter else Ownership.MY_BENCH
    return Ownership.OPPONENT if is_starter else None
