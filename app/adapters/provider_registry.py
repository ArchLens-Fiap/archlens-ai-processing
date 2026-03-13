import structlog

from app.config import get_settings
from app.domain.ports import AIProviderPort
from app.adapters.openai_provider import OpenAIProvider
from app.adapters.gemini_provider import GeminiProvider
from app.adapters.claude_provider import ClaudeProvider

logger = structlog.get_logger()


class ProviderRegistry:

    def __init__(self):
        self._providers: list[AIProviderPort] = []
        self._initialize()

    def _initialize(self):
        settings = get_settings()

        if settings.openai_api_key:
            self._providers.append(OpenAIProvider(provider_name="openai-gpt4o", model="gpt-4o", weight=1.0))
            logger.info("Registered AI provider", provider="openai-gpt4o", model="gpt-4o")

            self._providers.append(OpenAIProvider(provider_name="openai-gpt4o-mini", model="gpt-4o-mini", weight=0.8))
            logger.info("Registered AI provider", provider="openai-gpt4o-mini", model="gpt-4o-mini")

        if settings.google_ai_api_key:
            self._providers.append(GeminiProvider())
            logger.info("Registered AI provider", provider="gemini")

        if settings.anthropic_api_key:
            self._providers.append(ClaudeProvider())
            logger.info("Registered AI provider", provider="claude")

        if not self._providers:
            logger.warning("No AI providers configured")

    @property
    def providers(self) -> list[AIProviderPort]:
        return self._providers

    @property
    def active_count(self) -> int:
        return len(self._providers)
