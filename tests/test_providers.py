import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import ProviderResponse


class TestOpenAIProviderParseResponse:
    def test_parse_valid_json(self):
        from app.adapters.openai_provider import OpenAIProvider

        raw = json.dumps({
            "components": [{"name": "API", "type": "gateway"}],
            "scores": {"scalability": 7, "security": 8, "reliability": 6, "maintainability": 7, "overall": 7},
        })
        result = OpenAIProvider._parse_response(raw)
        assert len(result.components) == 1
        assert result.components[0].name == "API"

    def test_parse_invalid_json(self):
        from app.adapters.openai_provider import OpenAIProvider

        result = OpenAIProvider._parse_response("not json at all")
        assert result.components == []
        assert result.raw_response == "not json at all"

    def test_parse_empty_json(self):
        from app.adapters.openai_provider import OpenAIProvider

        result = OpenAIProvider._parse_response("{}")
        assert result.components == []

    def test_parse_json_with_all_fields(self):
        from app.adapters.openai_provider import OpenAIProvider

        raw = json.dumps({
            "components": [{"name": "Redis", "type": "cache", "description": "In-memory store", "technology": "Redis 7"}],
            "connections": [{"source": "API", "target": "Redis", "protocol": "TCP"}],
            "risks": [{"severity": "high", "category": "reliability", "title": "SPOF", "description": "No replica", "recommendation": "Add replica"}],
            "recommendations": ["Add replicas"],
            "scores": {"scalability": 8, "security": 7, "reliability": 6, "maintainability": 8, "overall": 7.25},
        })
        result = OpenAIProvider._parse_response(raw)
        assert len(result.components) == 1
        assert len(result.connections) == 1
        assert len(result.risks) == 1
        assert result.scores.scalability == 8


class TestClaudeProviderParseResponse:
    def test_parse_valid_json(self):
        from app.adapters.claude_provider import ClaudeProvider

        raw = json.dumps({
            "components": [{"name": "DB", "type": "database"}],
            "scores": {"scalability": 6, "security": 7, "reliability": 8, "maintainability": 6, "overall": 6.75},
        })
        result = ClaudeProvider._parse_response(raw)
        assert len(result.components) == 1

    def test_parse_json_wrapped_in_code_block(self):
        from app.adapters.claude_provider import ClaudeProvider

        raw = '```json\n{"components": [{"name": "API", "type": "service"}], "scores": {"scalability": 5, "security": 5, "reliability": 5, "maintainability": 5, "overall": 5}}\n```'
        result = ClaudeProvider._parse_response(raw)
        assert len(result.components) == 1
        assert result.components[0].name == "API"

    def test_parse_json_wrapped_in_generic_code_block(self):
        from app.adapters.claude_provider import ClaudeProvider

        raw = '```\n{"components": [{"name": "Svc", "type": "microservice"}], "scores": {"scalability": 5, "security": 5, "reliability": 5, "maintainability": 5, "overall": 5}}\n```'
        result = ClaudeProvider._parse_response(raw)
        assert len(result.components) == 1

    def test_parse_invalid_json(self):
        from app.adapters.claude_provider import ClaudeProvider

        result = ClaudeProvider._parse_response("This is not valid JSON")
        assert result.components == []
        assert result.provider_name == "claude"

    def test_parse_empty_string(self):
        from app.adapters.claude_provider import ClaudeProvider

        result = ClaudeProvider._parse_response("")
        assert result.components == []


class TestGeminiProviderParseResponse:
    def test_parse_valid_json(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": "Queue", "type": "queue"}],
            "scores": {"scalability": 9, "security": 7, "reliability": 8, "maintainability": 7, "overall": 7.75},
        })
        result = GeminiProvider._parse_response(raw)
        assert len(result.components) == 1

    def test_parse_coerces_string_scores(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": "API", "type": "gateway"}],
            "scores": {"scalability": "8", "security": "7", "reliability": "6", "maintainability": "7", "overall": "7"},
        })
        result = GeminiProvider._parse_response(raw)
        assert result.scores.scalability == 8.0
        assert result.scores.security == 7.0

    def test_parse_coerces_invalid_score_to_default(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": "API", "type": "gateway"}],
            "scores": {"scalability": "not_a_number", "security": 7, "reliability": 6, "maintainability": 7, "overall": 7},
        })
        result = GeminiProvider._parse_response(raw)
        assert result.scores.scalability == 5.0

    def test_parse_fixes_missing_risk_fields(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": "API", "type": "gateway"}],
            "risks": [{"severity": "high", "title": "SPOF"}],
            "scores": {"scalability": 7, "security": 7, "reliability": 7, "maintainability": 7, "overall": 7},
        })
        result = GeminiProvider._parse_response(raw)
        assert len(result.risks) == 1
        assert result.risks[0].category == ""
        assert result.risks[0].description == ""

    def test_parse_fixes_non_string_fields(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": 123, "type": "gateway", "description": 456}],
            "scores": {"scalability": 7, "security": 7, "reliability": 7, "maintainability": 7, "overall": 7},
        })
        result = GeminiProvider._parse_response(raw)
        assert result.components[0].name == "123"

    def test_parse_invalid_json(self):
        from app.adapters.gemini_provider import GeminiProvider

        result = GeminiProvider._parse_response("{invalid}")
        assert result.components == []
        assert result.provider_name == "gemini"

    def test_parse_fixes_missing_component_fields(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": "API"}],
            "scores": {"scalability": 7, "security": 7, "reliability": 7, "maintainability": 7, "overall": 7},
        })
        result = GeminiProvider._parse_response(raw)
        assert result.components[0].type == ""

    def test_parse_fixes_missing_connection_fields(self):
        from app.adapters.gemini_provider import GeminiProvider

        raw = json.dumps({
            "components": [{"name": "A", "type": "svc"}],
            "connections": [{"source": "A"}],
            "scores": {"scalability": 7, "security": 7, "reliability": 7, "maintainability": 7, "overall": 7},
        })
        result = GeminiProvider._parse_response(raw)
        assert result.connections[0].target == ""
