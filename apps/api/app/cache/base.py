"""Cache interface. v1 is backed by a Postgres TTL table; Redis can implement the same
Protocol when live polling volume demands it."""

from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...

    def delete(self, key: str) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...
