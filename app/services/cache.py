import json
import os
import time
from typing import Any, Optional


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
        payload = json.dumps(value)
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
