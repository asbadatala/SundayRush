from sqlmodel import Session

from app.config import get_settings
from app.domain.models import User
from app.domain.normalized import (
    NormalizedFantasyTeam,
    NormalizedLeague,
    NormalizedMatchup,
    NormalizedRoster,
    NormalizedScoringRules,
)
from app.nfl_data.composite import fixture_root
from app.providers.yahoo import parse
from app.providers.yahoo.client import FixtureYahooClient, YahooClient, YahooHttp
from app.providers.yahoo.oauth import ensure_fresh_token
from app.providers.yahoo.stat_map import to_scoring_rules


class YahooAdapter:
    provider = "yahoo"

    def __init__(self, client: YahooHttp):
        self.client = client

    def get_leagues(self) -> list[NormalizedLeague]:
        return parse.parse_leagues(self.client.get("users;use_login=1/games;game_keys=nfl/leagues"))

    def get_league(self, league_id: str) -> NormalizedLeague:
        return parse.parse_league(self.client.get(f"league/{league_id}"))

    def get_teams(self, league_id: str) -> list[NormalizedFantasyTeam]:
        return parse.parse_teams(self.client.get(f"league/{league_id}/teams"))

    def get_roster(self, team_id: str, week: int) -> NormalizedRoster:
        return parse.parse_roster(self.client.get(f"team/{team_id}/roster;week={week}"), week)

    def get_matchups(self, league_id: str, week: int) -> list[NormalizedMatchup]:
        return parse.parse_scoreboard(self.client.get(f"league/{league_id}/scoreboard;week={week}"), week)

    def get_scoring_rules(self, league_id: str) -> NormalizedScoringRules:
        categories, modifiers = parse.parse_settings(self.client.get(f"league/{league_id}/settings"))
        return to_scoring_rules(categories, modifiers)


def yahoo_adapter_for(db: Session, user: User) -> YahooAdapter:
    def get_token(force: bool) -> str:
        return ensure_fresh_token(db, user, force=force)

    if get_settings().fixture_mode:
        return YahooAdapter(FixtureYahooClient(fixture_root() / "yahoo", get_token))
    return YahooAdapter(YahooClient(get_token))
