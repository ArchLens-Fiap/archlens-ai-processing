import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.infrastructure.vector_store import VectorStore, EMBEDDING_DIM


def _fake_embedding(seed: int = 0) -> list[float]:
    """Generate a deterministic fake embedding vector."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(EMBEDDING_DIM).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


class TestVectorStoreAvailability:
    @patch("app.infrastructure.vector_store.get_settings")
    def test_not_available_without_openai_key(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="", redis_url="redis://localhost")
        vs = VectorStore()
        assert vs.available is False

    @patch("app.infrastructure.vector_store.get_settings")
    def test_available_with_openai_key(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()
        assert vs.available is True


class TestVectorStoreIndex:
    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_index_returns_zero_when_unavailable(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="", redis_url="redis://localhost")
        vs = VectorStore()
        count = await vs.index_analysis("a1", {"components": [{"name": "API", "type": "gw", "description": "x"}]})
        assert count == 0

    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_index_returns_zero_for_empty_result(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()
        count = await vs.index_analysis("a1", {})
        assert count == 0

    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_index_handles_embedding_failure(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()
        vs._openai = AsyncMock()
        vs._openai.embeddings.create.side_effect = RuntimeError("API error")

        count = await vs.index_analysis("a1", {"components": [{"name": "X", "type": "svc", "description": "y"}]})
        assert count == 0

    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_index_stores_chunks(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()

        # Mock OpenAI embeddings
        mock_embedding_data = MagicMock()
        mock_embedding_data.data = [MagicMock(embedding=_fake_embedding(i)) for i in range(2)]
        vs._openai = AsyncMock()
        vs._openai.embeddings.create.return_value = mock_embedding_data

        # Mock Redis pipeline
        mock_pipe = AsyncMock()
        vs._redis = AsyncMock()
        vs._redis.pipeline.return_value = mock_pipe

        data = {
            "components": [{"name": "API", "type": "gateway", "description": "Entry"}],
            "risks": [{"severity": "high", "category": "security", "title": "SPOF", "description": "No failover", "recommendation": "Fix"}],
        }
        count = await vs.index_analysis("a1", data)
        assert count == 2
        assert mock_pipe.hset.call_count == 2
        assert mock_pipe.expire.call_count == 2
        mock_pipe.execute.assert_called_once()


class TestVectorStoreSearch:
    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_search_returns_empty_when_unavailable(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="", redis_url="redis://localhost")
        vs = VectorStore()
        results = await vs.search("a1", "what are the risks?")
        assert results == []

    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_search_handles_embedding_failure(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()
        vs._openai = AsyncMock()
        vs._openai.embeddings.create.side_effect = RuntimeError("API error")

        results = await vs.search("a1", "query")
        assert results == []

    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_search_returns_ranked_results(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()

        # Mock query embedding
        query_vec = _fake_embedding(42)
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=query_vec)]
        vs._openai = AsyncMock()
        vs._openai.embeddings.create.return_value = mock_response

        # Mock Redis scan with stored vectors
        similar_vec = np.array(query_vec, dtype=np.float32)  # identical = perfect match
        different_vec = np.array(_fake_embedding(99), dtype=np.float32)

        async def fake_scan_iter(match=None):
            yield b"rag:a1:0"
            yield b"rag:a1:1"

        async def fake_hgetall(key):
            if key == b"rag:a1:0":
                return {b"text": b"Risk: SPOF detected", b"embedding": similar_vec.tobytes()}
            return {b"text": b"Score: 7/10", b"embedding": different_vec.tobytes()}

        vs._redis = AsyncMock()
        vs._redis.scan_iter = fake_scan_iter
        vs._redis.hgetall = fake_hgetall

        results = await vs.search("a1", "risks", top_k=2)
        assert len(results) == 2
        # The identical vector should rank first
        assert results[0] == "Risk: SPOF detected"

    @pytest.mark.asyncio
    @patch("app.infrastructure.vector_store.get_settings")
    async def test_search_respects_top_k(self, mock_settings):
        mock_settings.return_value = MagicMock(openai_api_key="sk-test", openai_base_url="", redis_url="redis://localhost")
        vs = VectorStore()

        query_vec = _fake_embedding(0)
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=query_vec)]
        vs._openai = AsyncMock()
        vs._openai.embeddings.create.return_value = mock_response

        vec = np.array(query_vec, dtype=np.float32)

        async def fake_scan_iter(match=None):
            for i in range(10):
                yield f"rag:a1:{i}".encode()

        async def fake_hgetall(key):
            return {b"text": f"Chunk {key}".encode(), b"embedding": vec.tobytes()}

        vs._redis = AsyncMock()
        vs._redis.scan_iter = fake_scan_iter
        vs._redis.hgetall = fake_hgetall

        results = await vs.search("a1", "query", top_k=3)
        assert len(results) == 3
