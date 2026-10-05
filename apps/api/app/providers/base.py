"""Fantasy provider adapter interface (spec §12)."""

from typing import Protocol

from app.domain.normalized import (
    NormalizedFantasyTeam,
    NormalizedLeague,
    NormalizedMatchup,
    NormalizedRoster,
    NormalizedScoringRules,
)


class FantasyProviderAdapter(Protocol):
    provider: str

    def get_leagues(self) -> list[NormalizedLeague]: ...

    def get_league(self, league_id: str) -> NormalizedLeague: ...

    def get_teams(self, league_id: str) -> list[NormalizedFantasyTeam]: ...

    def get_roster(self, team_id: str, week: int) -> NormalizedRoster: ...

    def get_matchups(self, league_id: str, week: int) -> list[NormalizedMatchup]: ...

    def get_scoring_rules(self, league_id: str) -> NormalizedScoringRules: ...
