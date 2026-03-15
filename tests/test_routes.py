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


class TestChatEndpoint:
    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_missing_fields(self, mock_get_service, mock_get_cache):
        from app.main import app
        client = TestClient(app)

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_get_service.return_value = mock_service

        response = client.post("/api/chat", json={})
        assert response.status_code == 422 or response.status_code == 400

    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_no_providers(self, mock_get_service, mock_get_cache):
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

    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_success_with_cached_result(self, mock_get_service, mock_get_cache):
        from app.main import app
        client = TestClient(app)

        mock_provider = AsyncMock()
        mock_provider.chat.return_value = "The main risk is SPOF."

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_service.first_provider = mock_provider
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

    @patch("app.api.routes.get_cache")
    @patch("app.api.routes.get_analysis_service")
    def test_chat_success_without_cached_result(self, mock_get_service, mock_get_cache):
        from app.main import app
        client = TestClient(app)

        mock_provider = AsyncMock()
        mock_provider.chat.return_value = "I don't have analysis data."

        mock_service = MagicMock()
        mock_service.has_providers = True
        mock_service.first_provider = mock_provider
        mock_get_service.return_value = mock_service

        mock_cache = AsyncMock()
        mock_cache.get_by_analysis.return_value = None
        mock_get_cache.return_value = mock_cache

        response = client.post("/api/chat", json={
            "analysis_id": "xyz789",
            "question": "Explain the architecture",
        })
        assert response.status_code == 200
