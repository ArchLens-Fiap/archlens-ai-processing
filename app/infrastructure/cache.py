import json

import redis.asyncio as aioredis
import structlog

from app.config import get_settings

logger = structlog.get_logger()

CACHE_TTL = 86400


class AnalysisCache:
    def __init__(self):
        settings = get_settings()
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, file_hash: str) -> dict | None:
        cached = await self._redis.get(f"analysis:{file_hash}")
        if cached:
            logger.info("Cache hit", file_hash=file_hash)
            return json.loads(cached)
        return None

    async def set(self, file_hash: str, result: dict) -> None:
        await self._redis.set(f"analysis:{file_hash}", json.dumps(result), ex=CACHE_TTL)
        logger.info("Cached analysis result", file_hash=file_hash, ttl=CACHE_TTL)

    async def close(self) -> None:
        await self._redis.aclose()
