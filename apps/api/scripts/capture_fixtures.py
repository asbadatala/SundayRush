"""Record real provider responses into tests/fixtures so tests never hit live services.

NFL (no auth):
    uv run python -m scripts.capture_fixtures nfl --season 2026 --week 4

Yahoo (uses the stored, encrypted token of an existing anonymous user; names are scrubbed):
    uv run python -m scripts.capture_fixtures yahoo --user-id <uuid> --league <league_key> --week 4
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session

from app.db import get_engine
from app.domain.models import User
from app.nfl_data.espn_schedule import ESPN_SCOREBOARD
from app.nfl_data.sleeper_players import FANTASY_POSITIONS, SLEEPER_BASE
from app.nfl_data.sleeper_stats import SLEEPER_STATS_BASE
from app.providers.yahoo.client import YahooClient, fixture_name
from app.providers.yahoo.oauth import ensure_fresh_token

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
PLAYER_FIELDS = (
    "player_id", "first_name", "last_name", "full_name", "position", "team", "status", "active",
    "injury_status", "gsis_id", "espn_id", "yahoo_id", "sportradar_id", "search_rank",
)  # fmt: skip
ESPN_EVENT_KEEP = ("id", "date", "shortName", "status")
ESPN_COMPETITION_KEEP = ("id", "date", "broadcasts", "geoBroadcasts")


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {path.relative_to(ROOT.parent.parent)} ({path.stat().st_size // 1024} KB)")


def _trim_espn(payload: dict[str, Any]) -> dict[str, Any]:
    events = []
    for e in payload.get("events", []):
        comp = e["competitions"][0]
        events.append(
            {
                **{k: e[k] for k in ESPN_EVENT_KEEP if k in e},
                "competitions": [
                    {
                        **{k: comp[k] for k in ESPN_COMPETITION_KEEP if k in comp},
                        "competitors": [
                            {
                                "homeAway": c["homeAway"],
                                "score": c.get("score"),
                                "team": {"abbreviation": c["team"]["abbreviation"]},
                            }
                            for c in comp["competitors"]
                        ],
                    }
                ],
            }
        )
    return {"events": events}


def capture_nfl(season: int, week: int) -> None:
    http = httpx.Client(timeout=60)
    nfl = ROOT / "nfl"
    _write(nfl / "sleeper_state.json", http.get(f"{SLEEPER_BASE}/state/nfl").json())

    players = http.get(f"{SLEEPER_BASE}/players/nfl").json()
    kept = {
        pid: {k: p.get(k) for k in PLAYER_FIELDS}
        for pid, p in players.items()
        if p.get("position") in FANTASY_POSITIONS and p.get("team")
    }
    _write(nfl / "sleeper_players.json", kept)

    stats = http.get(f"{SLEEPER_STATS_BASE}/{season}/{week}", params={"season_type": "regular"}).json()
    _write(
        nfl / f"sleeper_stats_{season}_{week}.json",
        [
            {"player_id": r["player_id"], "team": r.get("team"), "stats": r.get("stats") or {}}
            for r in stats
            if r.get("player_id") in kept
        ],
    )

    board = http.get(ESPN_SCOREBOARD, params={"dates": season, "seasontype": 2, "week": week}).json()
    _write(nfl / f"espn_scoreboard_{season}_{week}.json", _trim_espn(board))


_SCRUB_KEYS = {"nickname", "guid", "email", "image_url", "felo_score", "felo_tier"}


def _scrub(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: ("REDACTED" if k in _SCRUB_KEYS else _scrub(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node


def capture_yahoo(user_id: str, league_key: str, week: int) -> None:
    with Session(get_engine()) as db:
        user = db.get(User, user_id)
        if user is None:
            raise SystemExit(f"No user {user_id}")
        client = YahooClient(lambda force: ensure_fresh_token(db, user, force=force))
        paths = [
            "users;use_login=1/games;game_keys=nfl/leagues",
            f"league/{league_key}/settings",
            f"league/{league_key}/teams",
            f"league/{league_key}/scoreboard;week={week}",
        ]
        teams = client.get(f"league/{league_key}/teams")
        for team_key in re.findall(r'"team_key":\s*"([^"]+)"', json.dumps(teams)):
            paths.append(f"team/{team_key}/roster;week={week}")
        for path in dict.fromkeys(paths):
            _write(ROOT / "yahoo" / fixture_name(path), _scrub(client.get(path)))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("nfl")
    n.add_argument("--season", type=int, required=True)
    n.add_argument("--week", type=int, required=True)
    y = sub.add_parser("yahoo")
    y.add_argument("--user-id", required=True)
    y.add_argument("--league", required=True)
    y.add_argument("--week", type=int, required=True)
    args = parser.parse_args()
    if args.cmd == "nfl":
        capture_nfl(args.season, args.week)
    else:
        capture_yahoo(args.user_id, args.league, args.week)


if __name__ == "__main__":
    main()
