import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://sundayrush:sundayrush@localhost:5442/sundayrush_test")
os.environ["FIXTURE_MODE"] = "1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(*parts: str) -> Any:
    return json.loads(FIXTURES.joinpath(*parts).read_text())


@pytest.fixture(scope="session")
def engine() -> Any:
    from alembic import command
    from alembic.config import Config

    from app.db import get_engine

    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    command.upgrade(cfg, "head")

    eng = get_engine()
    from app.nfl_data.composite import FixtureNFLDataProvider
    from app.nfl_data.sync import sync_players

    with Session(eng) as s:
        sync_players(s, FixtureNFLDataProvider(FIXTURES))
    return eng


_USER_TABLES = (
    '"user", provider_connection, scoring_profile, fantasy_league, fantasy_team, roster_snapshot, '
    "roster_entry, fantasy_matchup, nfl_game, player_game_stats, player_id_mapping, cache_entry"
)


@pytest.fixture
def db(engine: Any) -> Iterator[Session]:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {_USER_TABLES} RESTART IDENTITY CASCADE"))
    from app.cache.db_cache import DbCache

    with Session(engine, expire_on_commit=False) as s:
        # Players catalog is loaded once per session; mark it fresh so nothing refetches.
        DbCache(s).set("nfl:players:synced", "fixture", 10**7)
        yield s


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app, base_url="http://testserver") as c:
        yield c


def player_id(db: Session, name: str) -> int:
    from sqlmodel import select

    from app.domain.models import CanonicalPlayer

    pid = db.exec(select(CanonicalPlayer.id).where(CanonicalPlayer.full_name == name)).first()
    assert pid is not None, name
    return pid
