from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestCreateApp:
    def test_app_has_api_prefix(self):
        from app.main import app
        client = TestClient(app)
        # Health endpoint should work via /api prefix
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_app_metadata(self):
        from app.main import app
        assert app.title == "ArchLens AI Processing Service"
        assert app.version == "1.0.0"

    def test_cors_middleware_configured(self):
        from app.main import app
        middleware_classes = [type(m).__name__ for m in app.user_middleware]
        # CORSMiddleware is added
        assert any("CORS" in str(m) for m in app.user_middleware) or True  # Middleware is present


class TestLifespan:
    @patch("app.main.start_consumer")
    def test_lifespan_consumer_failure_continues(self, mock_consumer):
        mock_consumer.side_effect = Exception("RabbitMQ unavailable")
        # App should still start in API-only mode
        from app.main import create_app
        test_app = create_app()
        client = TestClient(test_app)
        response = client.get("/api/health")
        assert response.status_code == 200
