from datetime import timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col

from app.domain.models import CacheEntry, utcnow


class DbCache:
    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str) -> Any | None:
        entry = self.session.get(CacheEntry, key, populate_existing=True)
        if entry is None or entry.expires_at <= utcnow():
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        now = utcnow()
        stmt = insert(CacheEntry).values(
            key=key, value=value, expires_at=now + timedelta(seconds=ttl_seconds), updated_at=now
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"value": stmt.excluded.value, "expires_at": stmt.excluded.expires_at, "updated_at": now},
        )
        self.session.execute(stmt)
        self.session.commit()

    def delete(self, key: str) -> None:
        self.session.execute(delete(CacheEntry).where(col(CacheEntry.key) == key))
        self.session.commit()

    def delete_prefix(self, prefix: str) -> None:
        self.session.execute(delete(CacheEntry).where(col(CacheEntry.key).startswith(prefix)))
        self.session.commit()
