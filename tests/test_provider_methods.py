"""Tests for provider analyze_diagram and chat methods using mocks."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import ProviderResponse


class TestOpenAIProviderAnalyze:
    @patch("app.adapters.openai_provider.get_settings")
    @patch("app.adapters.openai_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_diagram_success(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")

        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "components": [{"name": "API", "type": "gateway"}],
            "scores": {"scalability": 7, "security": 7, "reliability": 7, "maintainability": 7, "overall": 7},
        })
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client = AsyncMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"image-bytes", "test.png")
        assert result.provider_name == "openai"
        assert len(result.components) == 1

    @patch("app.adapters.openai_provider.get_settings")
    @patch("app.adapters.openai_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_chat_success(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")

        mock_choice = MagicMock()
        mock_choice.message.content = "Here is my analysis response."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client = AsyncMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.chat("context", "What are the risks?", [])
        assert result == "Here is my analysis response."

    @patch("app.adapters.openai_provider.get_settings")
    def test_openai_provider_properties(self, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test", provider_name="custom-openai", weight=0.8)
        assert provider.name == "custom-openai"
        assert provider.weight == 0.8

    @patch("app.adapters.openai_provider.get_settings")
    @patch("app.adapters.openai_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_jpeg_mime_type(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")

        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "components": [{"name": "DB", "type": "database"}],
            "scores": {"scalability": 5, "security": 5, "reliability": 5, "maintainability": 5, "overall": 5},
        })
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client = AsyncMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"jpeg-bytes", "test.jpg")
        assert result.provider_name == "openai"


class TestClaudeProviderAnalyze:
    @patch("app.adapters.claude_provider.get_settings")
    @patch("app.adapters.claude_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_diagram_success(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.anthropic_api_key = "sk-ant-test"
        settings.anthropic_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-ant-test")

        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "components": [{"name": "Queue", "type": "queue"}],
            "scores": {"scalability": 8, "security": 7, "reliability": 9, "maintainability": 7, "overall": 7.75},
        })
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        provider._client = AsyncMock()
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"img-bytes", "arch.png")
        assert result.provider_name == "claude"
        assert len(result.components) == 1

    @patch("app.adapters.claude_provider.get_settings")
    @patch("app.adapters.claude_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_webp_mime_type(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.anthropic_api_key = "sk-ant-test"
        settings.anthropic_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-ant-test")

        mock_content = MagicMock()
        mock_content.text = '{"components": [{"name": "A", "type": "svc"}], "scores": {"scalability": 5, "security": 5, "reliability": 5, "maintainability": 5, "overall": 5}}'
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        provider._client = AsyncMock()
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"webp-bytes", "arch.webp")
        assert result.provider_name == "claude"

    @patch("app.adapters.claude_provider.get_settings")
    @patch("app.adapters.claude_provider.load_prompt", return_value="prompt")
    @pytest.mark.asyncio
    async def test_chat_success(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.anthropic_api_key = "sk-ant-test"
        settings.anthropic_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-ant-test")

        mock_content = MagicMock()
        mock_content.text = "The architecture looks solid."
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        provider._client = AsyncMock()
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.chat("context", "How is the architecture?", [{"role": "user", "content": "hi"}])
        assert result == "The architecture looks solid."

    @patch("app.adapters.claude_provider.get_settings")
    @patch("app.adapters.claude_provider.load_prompt", return_value="prompt")
    @pytest.mark.asyncio
    async def test_chat_empty_response(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.anthropic_api_key = "sk-ant-test"
        settings.anthropic_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.content = []

        provider._client = AsyncMock()
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.chat("ctx", "question", [])
        assert result == ""

    @patch("app.adapters.claude_provider.get_settings")
    def test_claude_provider_properties(self, mock_settings):
        settings = MagicMock()
        settings.anthropic_api_key = "key"
        settings.anthropic_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="key")
        assert provider.name == "claude"
        assert provider.weight == 1.0

    @patch("app.adapters.claude_provider.get_settings")
    @patch("app.adapters.claude_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_empty_content(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.anthropic_api_key = "sk-ant-test"
        settings.anthropic_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.claude_provider import ClaudeProvider

        provider = ClaudeProvider(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.content = []

        provider._client = AsyncMock()
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"img", "test.png")
        assert result.components == []


class TestOpenAIProviderAnalyzeEmptyContent:
    @patch("app.adapters.openai_provider.get_settings")
    @patch("app.adapters.openai_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_empty_content(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client = AsyncMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"img", "test.png")
        assert result.components == []

    @patch("app.adapters.openai_provider.get_settings")
    @patch("app.adapters.openai_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_chat_empty_content(self, mock_prompt, mock_settings):
        settings = MagicMock()
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = ""
        mock_settings.return_value = settings

        from app.adapters.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client = AsyncMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.chat("ctx", "q", [])
        assert result == ""
