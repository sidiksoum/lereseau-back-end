import json
import os
import time
from datetime import date, datetime, time as dt_time
from enum import Enum
from typing import Any, Optional


def make_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): make_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_jsonable(item) for item in value]
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return make_jsonable(value.model_dump())
    if hasattr(value, "__dict__"):
        data = {}
        for key, item in vars(value).items():
            if key.startswith("_"):
                continue
            data[key] = make_jsonable(item)
        return data
    return str(value)


class CacheService:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self._local_cache: dict[str, tuple[float, Any]] = {}
        self._redis_client = None

        if self.redis_url:
            try:
                import redis

                self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
                self._redis_client.ping()
            except Exception as exc:  # pragma: no cover - environment-dependent
                self._redis_client = None
                print(f"[CACHE] Redis indisponible, fallback mémoire activé: {exc}")

    def get(self, key: str) -> Any:
        if self._redis_client:
            try:
                payload = self._redis_client.get(key)
                if payload is None:
                    return None
                return json.loads(payload)
            except Exception:
                pass

        entry = self._local_cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            self._local_cache.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        payload = json.dumps(make_jsonable(value))
        if self._redis_client:
            try:
                self._redis_client.setex(key, ttl, payload)
                return
            except Exception:
                pass

        expires_at = time.time() + ttl
        self._local_cache[key] = (expires_at, value)

    def delete(self, key: str) -> None:
        if self._redis_client:
            try:
                self._redis_client.delete(key)
            except Exception:
                pass
        self._local_cache.pop(key, None)


cache = CacheService(redis_url=os.getenv("REDIS_URL"))
