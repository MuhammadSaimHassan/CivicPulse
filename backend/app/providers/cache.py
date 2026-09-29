"""Redis, behind a small interface.

Redis does two jobs in this system (read-through cache, distributed rate
limiter) plus some shared bookkeeping (triage outcome ring buffer, cache hit
counters). A cache outage must degrade the system, not break it, so every
method here swallows Redis errors, logs them once, and reports a miss.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import redis

log = logging.getLogger(__name__)


class Cache(Protocol):
    def get_json(self, key: str) -> Any | None: ...
    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def delete(self, *keys: str) -> None: ...
    def incr(self, key: str) -> int: ...
    def get_int(self, key: str) -> int: ...
    def push_capped(self, key: str, value: Any, cap: int) -> None: ...
    def list_json(self, key: str, limit: int) -> list[Any]: ...
    def ping(self) -> bool: ...


class RedisCache:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    @classmethod
    def from_url(cls, url: str) -> RedisCache:
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            health_check_interval=30,
            decode_responses=True,
        )
        return cls(client)

    @property
    def client(self) -> redis.Redis:
        return self._r

    def get_json(self, key: str) -> Any | None:
        try:
            raw = self._r.get(key)
        except redis.RedisError as exc:
            log.warning("cache get failed", extra={"key": key, "error": type(exc).__name__})
            return None
        return None if raw is None else json.loads(raw)  # type: ignore[arg-type]

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            self._r.set(key, json.dumps(value, default=str), ex=ttl_seconds)
        except redis.RedisError as exc:
            log.warning("cache set failed", extra={"key": key, "error": type(exc).__name__})

    def delete(self, *keys: str) -> None:
        try:
            self._r.delete(*keys)
        except redis.RedisError as exc:
            log.warning("cache delete failed", extra={"keys": keys, "error": type(exc).__name__})

    def incr(self, key: str) -> int:
        try:
            return int(self._r.incr(key))  # type: ignore[arg-type]
        except redis.RedisError:
            return 0

    def get_int(self, key: str) -> int:
        try:
            raw = self._r.get(key)
        except redis.RedisError:
            return 0
        return int(raw) if raw else 0  # type: ignore[arg-type]

    def push_capped(self, key: str, value: Any, cap: int) -> None:
        try:
            pipe = self._r.pipeline()
            pipe.lpush(key, json.dumps(value, default=str))
            pipe.ltrim(key, 0, cap - 1)
            pipe.execute()
        except redis.RedisError as exc:
            log.warning("cache push failed", extra={"key": key, "error": type(exc).__name__})

    def list_json(self, key: str, limit: int) -> list[Any]:
        try:
            items = self._r.lrange(key, 0, limit - 1)
        except redis.RedisError:
            return []
        return [json.loads(i) for i in items]  # type: ignore[union-attr]

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except redis.RedisError:
            return False

    def close(self) -> None:
        self._r.close()
