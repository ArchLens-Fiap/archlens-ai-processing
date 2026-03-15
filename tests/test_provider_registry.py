from unittest.mock import patch, MagicMock

from app.adapters.provider_registry import ProviderRegistry


class TestProviderRegistry:
    @patch("app.adapters.provider_registry.get_settings")
    @patch("app.adapters.provider_registry.OpenAIProvider")
    def test_registers_openai_when_key_present(self, mock_openai_cls, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.google_ai_api_key = ""
        settings.anthropic_api_key = ""
        mock_settings.return_value = settings

        registry = ProviderRegistry()
        # Two OpenAI providers (gpt-4o and gpt-4o-mini)
        assert registry.active_count == 2

    @patch("app.adapters.provider_registry.get_settings")
    @patch("app.adapters.provider_registry.GeminiProvider")
    def test_registers_gemini_when_key_present(self, mock_gemini_cls, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = ""
        settings.google_ai_api_key = "gemini-key"
        settings.anthropic_api_key = ""
        mock_settings.return_value = settings

        registry = ProviderRegistry()
        assert registry.active_count == 1

    @patch("app.adapters.provider_registry.get_settings")
    @patch("app.adapters.provider_registry.ClaudeProvider")
    def test_registers_claude_when_key_present(self, mock_claude_cls, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = ""
        settings.google_ai_api_key = ""
        settings.anthropic_api_key = "anthropic-key"
        mock_settings.return_value = settings

        registry = ProviderRegistry()
        assert registry.active_count == 1

    @patch("app.adapters.provider_registry.get_settings")
    def test_no_providers_when_no_keys(self, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = ""
        settings.google_ai_api_key = ""
        settings.anthropic_api_key = ""
        mock_settings.return_value = settings

        registry = ProviderRegistry()
        assert registry.active_count == 0
        assert registry.providers == []

    @patch("app.adapters.provider_registry.get_settings")
    @patch("app.adapters.provider_registry.OpenAIProvider")
    @patch("app.adapters.provider_registry.GeminiProvider")
    @patch("app.adapters.provider_registry.ClaudeProvider")
    def test_registers_all_providers(self, mock_claude, mock_gemini, mock_openai, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.google_ai_api_key = "gemini-key"
        settings.anthropic_api_key = "anthropic-key"
        mock_settings.return_value = settings

        registry = ProviderRegistry()
        # 2 openai + 1 gemini + 1 claude = 4
        assert registry.active_count == 4
