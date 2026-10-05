"""NFL data interface (spec §13), independent of fantasy providers.

Deviation from spec: the free sources publish stats per week rather than per game, so
`get_week_stats` replaces `getPlayerGameStats(gameId)`. Stats join to games through the
player's NFL team and the week schedule.
"""

from typing import Protocol

from app.domain.normalized import (
    NFLState,
    NormalizedNFLGame,
    NormalizedNFLPlayer,
    NormalizedPlayerStats,
)


class NFLDataProvider(Protocol):
    def get_state(self) -> NFLState: ...

    def get_players(self) -> list[NormalizedNFLPlayer]: ...

    def get_schedule(self, season: int, week: int) -> list[NormalizedNFLGame]: ...

    def get_week_stats(self, season: int, week: int) -> list[NormalizedPlayerStats]: ...
