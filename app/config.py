from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    debug: bool = False

    # AI Providers
    openai_api_key: str = ""
    openai_base_url: str = ""
    google_ai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "archlens"
    rabbitmq_password: str = "archlens_dev_2026"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "archlens"
    minio_secret_key: str = "archlens_dev_2026"
    minio_bucket: str = "archlens-diagrams"
    minio_use_ssl: bool = False

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "archlens_dev_2026"
    redis_db: int = 0

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "archlens-ai-processing"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
