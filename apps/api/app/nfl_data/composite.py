import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.domain.normalized import (
    NFLState,
    NormalizedNFLGame,
    NormalizedNFLPlayer,
    NormalizedPlayerStats,
)
from app.errors import LiveDataUnavailable
from app.nfl_data.base import NFLDataProvider
from app.nfl_data.espn_schedule import ESPNScheduleClient, parse_scoreboard
from app.nfl_data.sleeper_players import SleeperPlayersClient, parse_players, parse_state
from app.nfl_data.sleeper_stats import SleeperStatsClient, parse_week_stats


class CompositeNFLDataProvider:
    """Sleeper for players/state/stats, ESPN for the schedule."""

    def __init__(
        self,
        players: SleeperPlayersClient | None = None,
        stats: SleeperStatsClient | None = None,
        schedule: ESPNScheduleClient | None = None,
    ):
        self._players = players or SleeperPlayersClient()
        self._stats = stats or SleeperStatsClient()
        self._schedule = schedule or ESPNScheduleClient()

    def get_state(self) -> NFLState:
        return self._players.get_state()

    def get_players(self) -> list[NormalizedNFLPlayer]:
        return self._players.get_players()

    def get_schedule(self, season: int, week: int) -> list[NormalizedNFLGame]:
        return self._schedule.get_schedule(season, week)

    def get_week_stats(self, season: int, week: int) -> list[NormalizedPlayerStats]:
        return self._stats.get_week_stats(season, week)


def fixture_root() -> Path:
    configured = get_settings().fixture_dir
    return Path(configured) if configured else Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class FixtureNFLDataProvider:
    """Reads recorded raw payloads from tests/fixtures/nfl and runs the real parsers."""

    def __init__(self, root: Path | None = None):
        self.root = (root or fixture_root()) / "nfl"

    def _load(self, name: str) -> Any:
        path = self.root / name
        if not path.exists():
            raise LiveDataUnavailable(f"No NFL fixture {name}.")
        return json.loads(path.read_text())

    def get_state(self) -> NFLState:
        return parse_state(self._load("sleeper_state.json"))

    def get_players(self) -> list[NormalizedNFLPlayer]:
        return parse_players(self._load("sleeper_players.json"))

    def get_schedule(self, season: int, week: int) -> list[NormalizedNFLGame]:
        return parse_scoreboard(self._load(f"espn_scoreboard_{season}_{week}.json"), season, week)

    def get_week_stats(self, season: int, week: int) -> list[NormalizedPlayerStats]:
        return parse_week_stats(self._load(f"sleeper_stats_{season}_{week}.json"))


_override: NFLDataProvider | None = None


def set_nfl_data_provider(provider: NFLDataProvider | None) -> None:
    """Test hook."""
    global _override
    _override = provider
    _default_provider.cache_clear()


@lru_cache
def _default_provider() -> NFLDataProvider:
    if get_settings().fixture_mode:
        return FixtureNFLDataProvider()
    return CompositeNFLDataProvider()


def get_nfl_data_provider() -> NFLDataProvider:
    return _override or _default_provider()
