"""Tests for GeminiProvider analyze_diagram and chat methods."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGeminiProviderAnalyze:
    @patch("app.adapters.gemini_provider.get_settings")
    @patch("app.adapters.gemini_provider.genai")
    @patch("app.adapters.gemini_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_diagram_success(self, mock_prompt, mock_genai, mock_settings):
        settings = MagicMock()
        settings.google_ai_api_key = "gemini-key"
        mock_settings.return_value = settings

        from app.adapters.gemini_provider import GeminiProvider

        provider = GeminiProvider.__new__(GeminiProvider)
        provider._model = AsyncMock()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "components": [{"name": "API", "type": "gateway"}],
            "scores": {"scalability": 7, "security": 7, "reliability": 7, "maintainability": 7, "overall": 7},
        })
        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"img-bytes", "test.png")
        assert result.provider_name == "gemini"
        assert len(result.components) == 1

    @patch("app.adapters.gemini_provider.get_settings")
    @patch("app.adapters.gemini_provider.genai")
    @patch("app.adapters.gemini_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_diagram_jpeg(self, mock_prompt, mock_genai, mock_settings):
        settings = MagicMock()
        settings.google_ai_api_key = "gemini-key"
        mock_settings.return_value = settings

        from app.adapters.gemini_provider import GeminiProvider

        provider = GeminiProvider.__new__(GeminiProvider)
        provider._model = AsyncMock()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "components": [{"name": "DB", "type": "database"}],
            "scores": {"scalability": 5, "security": 5, "reliability": 5, "maintainability": 5, "overall": 5},
        })
        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"jpeg-bytes", "diagram.jpg")
        assert result.provider_name == "gemini"

    @patch("app.adapters.gemini_provider.get_settings")
    @patch("app.adapters.gemini_provider.genai")
    @patch("app.adapters.gemini_provider.load_prompt", return_value="prompt")
    @pytest.mark.asyncio
    async def test_chat_success(self, mock_prompt, mock_genai, mock_settings):
        settings = MagicMock()
        settings.google_ai_api_key = "gemini-key"
        mock_settings.return_value = settings

        from app.adapters.gemini_provider import GeminiProvider

        provider = GeminiProvider.__new__(GeminiProvider)
        provider._model = AsyncMock()

        mock_response = MagicMock()
        mock_response.text = "The architecture has good separation."
        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.chat("context", "How is it?", [{"role": "user", "content": "hi"}])
        assert result == "The architecture has good separation."

    @patch("app.adapters.gemini_provider.get_settings")
    @patch("app.adapters.gemini_provider.genai")
    @patch("app.adapters.gemini_provider.load_prompt", return_value="prompt")
    @pytest.mark.asyncio
    async def test_chat_empty_response(self, mock_prompt, mock_genai, mock_settings):
        settings = MagicMock()
        settings.google_ai_api_key = "gemini-key"
        mock_settings.return_value = settings

        from app.adapters.gemini_provider import GeminiProvider

        provider = GeminiProvider.__new__(GeminiProvider)
        provider._model = AsyncMock()

        mock_response = MagicMock()
        mock_response.text = None
        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.chat("ctx", "q", [])
        assert result == ""

    @patch("app.adapters.gemini_provider.get_settings")
    @patch("app.adapters.gemini_provider.genai")
    @patch("app.adapters.gemini_provider.load_prompt", return_value="prompt text")
    @pytest.mark.asyncio
    async def test_analyze_empty_response(self, mock_prompt, mock_genai, mock_settings):
        settings = MagicMock()
        settings.google_ai_api_key = "gemini-key"
        mock_settings.return_value = settings

        from app.adapters.gemini_provider import GeminiProvider

        provider = GeminiProvider.__new__(GeminiProvider)
        provider._model = AsyncMock()

        mock_response = MagicMock()
        mock_response.text = None
        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.analyze_diagram(b"img", "test.png")
        assert result.components == []

    @patch("app.adapters.gemini_provider.get_settings")
    @patch("app.adapters.gemini_provider.genai")
    def test_gemini_provider_properties(self, mock_genai, mock_settings):
        settings = MagicMock()
        settings.google_ai_api_key = "key"
        mock_settings.return_value = settings

        from app.adapters.gemini_provider import GeminiProvider

        provider = GeminiProvider.__new__(GeminiProvider)
        # Set internal attributes manually since we bypassed __init__
        provider._model = MagicMock()

        assert GeminiProvider.name.fget(provider) == "gemini"
        assert GeminiProvider.weight.fget(provider) == 0.9
