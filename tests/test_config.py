import os
from unittest.mock import patch

from app.config import Settings


class TestSettings:
    @patch.dict(os.environ, {}, clear=True)
    def test_default_values(self):
        settings = Settings(
            _env_file=None,
            openai_api_key="",
            google_ai_api_key="",
            anthropic_api_key="",
            anthropic_base_url="",
            openai_base_url="",
        )
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.minio_bucket == "archlens-diagrams"

    def test_rabbitmq_url(self):
        settings = Settings(rabbitmq_user="user", rabbitmq_password="pass", rabbitmq_host="rmq", rabbitmq_port=5672)
        assert settings.rabbitmq_url == "amqp://user:pass@rmq:5672/"

    def test_redis_url(self):
        settings = Settings(redis_password="secret", redis_host="redis-host", redis_port=6380, redis_db=2)
        assert settings.redis_url == "redis://:secret@redis-host:6380/2"

    def test_minio_ssl_default_false(self):
        settings = Settings()
        assert settings.minio_use_ssl is False
