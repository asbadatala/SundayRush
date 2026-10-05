"""CLI: uv run python -m app.nfl_data.sync_players [--week SEASON WEEK]"""

import sys

from sqlmodel import Session

from app.config import get_settings
from app.db import get_engine
from app.logging import configure_logging
from app.nfl_data.sync import get_current_state, refresh_week, sync_players


def main(argv: list[str]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=False)
    with Session(get_engine()) as session:
        count = sync_players(session)
        print(f"Synced {count} players")
        if "--week" in argv:
            state = get_current_state(session)
            games = refresh_week(session, state.season, state.week)
            print(f"Loaded {len(games)} games for {state.season} week {state.week}")


if __name__ == "__main__":
    main(sys.argv[1:])
