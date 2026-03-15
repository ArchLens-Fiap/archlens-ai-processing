import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.cache import AnalysisCache, CACHE_TTL


class TestAnalysisCache:
    @patch("app.infrastructure.cache.get_settings")
    @patch("app.infrastructure.cache.aioredis")
    def _make_cache(self, mock_aioredis, mock_settings):
        settings = MagicMock()
        settings.redis_url = "redis://:pass@localhost:6379/0"
        mock_settings.return_value = settings
        mock_redis = AsyncMock()
        mock_aioredis.from_url.return_value = mock_redis
        cache = AnalysisCache()
        return cache, mock_redis

    @pytest.mark.asyncio
    async def test_get_cache_hit(self):
        cache, mock_redis = self._make_cache()
        expected = {"components": [{"name": "API"}]}
        mock_redis.get.return_value = json.dumps(expected)

        result = await cache.get("abc123hash")
        assert result == expected
        mock_redis.get.assert_called_once_with("analysis:abc123hash")

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        cache, mock_redis = self._make_cache()
        mock_redis.get.return_value = None

        result = await cache.get("unknown-hash")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_with_ttl(self):
        cache, mock_redis = self._make_cache()
        data = {"confidence": 0.8}

        await cache.set("hash123", data)
        mock_redis.set.assert_called_once_with(
            "analysis:hash123", json.dumps(data), ex=CACHE_TTL
        )

    @pytest.mark.asyncio
    async def test_get_by_analysis(self):
        cache, mock_redis = self._make_cache()
        expected = {"providers_used": ["openai"]}
        mock_redis.get.return_value = json.dumps(expected)

        result = await cache.get_by_analysis("analysis-001")
        assert result == expected
        mock_redis.get.assert_called_once_with("analysis_result:analysis-001")

    @pytest.mark.asyncio
    async def test_get_by_analysis_miss(self):
        cache, mock_redis = self._make_cache()
        mock_redis.get.return_value = None

        result = await cache.get_by_analysis("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_by_analysis(self):
        cache, mock_redis = self._make_cache()
        data = {"confidence": 0.9}

        await cache.set_by_analysis("analysis-002", data)
        mock_redis.set.assert_called_once_with(
            "analysis_result:analysis-002", json.dumps(data), ex=CACHE_TTL
        )

    @pytest.mark.asyncio
    async def test_close(self):
        cache, mock_redis = self._make_cache()
        await cache.close()
        mock_redis.aclose.assert_called_once()
