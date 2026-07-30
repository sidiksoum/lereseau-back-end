import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.cache import CacheService


def test_cache_service_fallback_round_trip():
    cache = CacheService(redis_url=None)
    cache.set("demo", {"ok": True}, ttl=60)
    assert cache.get("demo") == {"ok": True}


def test_background_jobs_run_in_order():
    async def main():
        cache = CacheService(redis_url=None)
        order = []

        async def worker(value: int):
            order.append(value)
            return value + 1

        from app.services.background_jobs import BackgroundJobService

        service = BackgroundJobService()
        await service.start()
        await service.enqueue(worker, 1)
        await service.enqueue(worker, 2)
        await asyncio.sleep(0.1)
        assert order == [1, 2]

    asyncio.run(main())
