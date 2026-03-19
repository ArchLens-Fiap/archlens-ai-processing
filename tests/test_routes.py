import asyncio
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import _build_context
from app.domain.models import ConsensusResult, Score


class TestBuildContext:
    def test_build_context_with_all_fields(self):
        data = {
            "components": [{"name": "API Gateway"}, {"name": "DB"}],
            "risks": [{"severity": "high", "title": "SPOF", "description": "No failover"}],
            "recommendations": ["Add replica"],
            "scores": {"scalability": 7, "security": 8, "reliability": 6, "maintainability": 7, "overall": 7},
            "confidence": 0.85,
            "providers_used": ["openai", "gemini"],
        }
        context = _build_context(data)
        assert "API Gateway" in context
        assert "SPOF" in context
        assert "Add replica" in context
        assert "scalability=7" in context
        assert "0.85" in context
        assert "openai" in context

    def test_build_context_empty_data(self):
        context = _build_context({})
        assert context == "No analysis data available."

    def test_build_context_only_components(self):
        data = {"components": [{"name": "Redis"}]}
        context = _build_context(data)
        assert "Redis" in context

    def test_build_context_many_components_truncated(self):
        comps = [{"name": f"Service-{i}"} for i in range(25)]
        data = {"components": comps}
        context = _build_context(data)
        assert "Components (25)" in context
        # Only first 20 names included
        assert "Service-0" in context
        assert "Service-19" in context

    def test_build_context_risks_truncated(self):
        risks = [{"severity": "medium", "title": f"Risk-{i}", "description": f"Desc-{i}"} for i in range(15)]
        data = {"risks": risks}
        context = _build_context(data)
        assert "Risks (15)" in context

    def test_build_context_no_confidence(self):
        data = {"components": [{"name": "A"}]}
        context = _build_context(data)
        assert "Confidence" not in context


class TestAnalyzeEndpoint:
    @patch("app.api.routes.get_analysis_service")
    def test_analyze_unsupported_file_type(self, mock_get_service):
        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/analyze",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    @patch("app.api.routes.get_analysis_service")
    def test_analyze_file_too_large(self, mock_get_service):
        from app.main import app
        client = TestClient(app)

        # Create a file just over 20MB
        large_data = b"x" * (20 * 1024 * 1024 + 1)
        response = client.post(
            "/api/analyze",
            files={"file": ("big.png", large_data, "image/png")},
        )
        assert response.status_code == 400
        assert "File too large" in response.json()["detail"]

    @patch("app.api.routes.get_analysis_service")
    def test_analyze_success(self, mock_get_service):
        from app.main import app
        client = TestClient(app)

        mock_service = AsyncMock()
        mock_service.analyze.return_value = ConsensusResult(
            confidence=0.8,
            providers_used=["openai"],
            scores=Score(scalability=7, security=7, reliability=7, maintainability=7, overall=7),
        )
        mock_get_service.return_value = mock_service

        # Create a small valid PNG
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="PNG")
        png_bytes = buf.getvalue()

        response = client.post(
            "/api/analyze",
            files={"file": ("diagram.png", png_bytes, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] == 0.8


class TestTieredFallback:
    @pytest.mark.asyncio
    async def test_try_chat_provider_success(self):
        from app.api.routes import _try_chat_provider

        provider = AsyncMock()
        provider.name = "openai-mini"
        provider.chat.return_value = "Hello!"

        result = await _try_chat_provider(provider, "ctx", "question", [], 8.0)
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_try_chat_provider_timeout(self):
        from app.api.routes import _try_chat_provider

        provider = AsyncMock()
        provider.name = "slow-provider"

        async def slow_chat(**kwargs):
            await asyncio.sleep(999)

        provider.chat = slow_chat

        result = await _try_chat_provider(provider, "ctx", "q", [], 0.01)
        assert result is None

    @pytest.mark.asyncio
    async def test_try_chat_provider_exception(self):
        from app.api.routes import _try_chat_provider

        provider = AsyncMock()
        provider.name = "broken"
        provider.chat.side_effect = RuntimeError("API crash")

        result = await _try_chat_provider(provider, "ctx", "q", [], 8.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_chat_with_fallback_first_succeeds(self):
        from app.api.routes import _chat_with_fallback

        p1 = AsyncMock()
        p1.name = "mini"
        p1.chat.return_value = "Fast response"

        p2 = AsyncMock()
        p2.name = "gemini"

        chunks = [chunk async for chunk in _chat_with_fallback([p1, p2], "ctx", "q", [])]
        assert any("Fast response" in c for c in chunks)
        assert any("[DONE]" in c for c in chunks)
        p2.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_with_fallback_first_fails_second_succeeds(self):
        from app.api.routes import _chat_with_fallback

        p1 = AsyncMock()
        p1.name = "mini"
        p1.chat.side_effect = RuntimeError("down")

        p2 = AsyncMock()
        p2.name = "gemini"
        p2.chat.return_value = "Fallback response"

        chunks = [chunk async for chunk in _chat_with_fallback([p1, p2], "ctx", "q", [])]
        assert any("Fallback response" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_chat_with_fallback_all_fail(self):
        from app.api.routes import _chat_with_fallback

        p1 = AsyncMock()
        p1.name = "mini"
        p1.chat.side_effect = RuntimeError("down")

        p2 = AsyncMock()
        p2.name = "gemini"
        p2.chat.side_effect = RuntimeError("also down")

        chunks = [chunk async for chunk in _chat_with_fallback([p1, p2], "ctx", "q", [])]
        assert any("All AI providers" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_chat_with_fallback_empty_providers(self):
        from app.api.routes import _chat_with_fallback

        chunks = [chunk async for chunk in _chat_with_fallback([], "ctx", "q", [])]
        assert any("All AI providers" in c for c in chunks)


def _mock_vector_store(available=False, search_results=None):
    """Create a mock VectorStore."""
    vs = AsyncMock()
    vs.available = available
    vs.search.return_value = search_results or []
    return vs


class TestChatEndpoint:
    @patch("app.api.routes.get_vector_store")
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_missing_fields(self, mock_get_service, mock_get_cache, mock_get_vs):
        from app.main import app
        client = TestClient(app)

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_get_service.return_value = mock_service

        response = client.post("/api/chat", json={})
        assert response.status_code == 422 or response.status_code == 400

    @patch("app.api.routes.get_vector_store")
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_no_providers(self, mock_get_service, mock_get_cache, mock_get_vs):
        from app.main import app
        client = TestClient(app)

        mock_service = MagicMock()
        mock_service.has_providers = False
        mock_get_service.return_value = mock_service

        response = client.post("/api/chat", json={
            "analysis_id": "abc123",
            "question": "What are the risks?",
        })
        assert response.status_code == 503

    @patch("app.api.routes.get_vector_store")
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_success_with_cached_result(self, mock_get_service, mock_get_cache, mock_get_vs):
        from app.main import app
        client = TestClient(app)

        mock_get_vs.return_value = _mock_vector_store(available=False)

        mock_provider = AsyncMock()
        mock_provider.name = "openai-mini"
        mock_provider.chat.return_value = "The main risk is SPOF."

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_service.chat_provider_chain = [mock_provider]
        mock_get_service.return_value = mock_service

        mock_cache = AsyncMock()
        mock_cache.get_by_analysis.return_value = {
            "components": [{"name": "API"}],
            "risks": [],
        }
        mock_get_cache.return_value = mock_cache

        response = client.post("/api/chat", json={
            "analysis_id": "abc123",
            "question": "What are the risks?",
        })
        assert response.status_code == 200
        assert "SPOF" in response.text

    @patch("app.api.routes.get_vector_store")
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_success_without_cached_result(self, mock_get_service, mock_get_cache, mock_get_vs):
        from app.main import app
        client = TestClient(app)

        mock_get_vs.return_value = _mock_vector_store(available=False)

        mock_provider = AsyncMock()
        mock_provider.name = "openai-mini"
        mock_provider.chat.return_value = "I don't have analysis data."

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_service.chat_provider_chain = [mock_provider]
        mock_get_service.return_value = mock_service

        mock_cache = AsyncMock()
        mock_cache.get_by_analysis.return_value = None
        mock_get_cache.return_value = mock_cache

        response = client.post("/api/chat", json={
            "analysis_id": "xyz789",
            "question": "Explain the architecture",
        })
        assert response.status_code == 200

    @patch("app.api.routes.get_vector_store")
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_uses_rag_when_available(self, mock_get_service, mock_get_cache, mock_get_vs):
        from app.main import app
        client = TestClient(app)

        mock_get_vs.return_value = _mock_vector_store(
            available=True,
            search_results=["Risk: SPOF detected", "Component: API Gateway"],
        )

        mock_provider = AsyncMock()
        mock_provider.name = "openai-mini"
        mock_provider.chat.return_value = "Based on the risks..."

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_service.chat_provider_chain = [mock_provider]
        mock_get_service.return_value = mock_service

        response = client.post("/api/chat", json={
            "analysis_id": "abc123",
            "question": "What are the risks?",
        })
        assert response.status_code == 200
        # Cache should NOT have been called since RAG provided context
        mock_get_cache.return_value.get_by_analysis.assert_not_called()

    @patch("app.api.routes.get_vector_store")
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_fallback_in_endpoint(self, mock_get_service, mock_get_cache, mock_get_vs):
        from app.main import app
        client = TestClient(app)

        mock_get_vs.return_value = _mock_vector_store(available=False)

        p1 = AsyncMock()
        p1.name = "mini"
        p1.chat.side_effect = RuntimeError("down")

        p2 = AsyncMock()
        p2.name = "gemini"
        p2.chat.return_value = "Gemini answered."

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_service.chat_provider_chain = [p1, p2]
        mock_get_service.return_value = mock_service

        mock_cache = AsyncMock()
        mock_cache.get_by_analysis.return_value = None
        mock_get_cache.return_value = mock_cache

        response = client.post("/api/chat", json={
            "analysis_id": "abc",
            "question": "test",
        })
        assert response.status_code == 200
        assert "Gemini answered" in response.text
