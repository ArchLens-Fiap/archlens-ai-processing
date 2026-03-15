import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.messaging.consumer import _consensus_to_result_json
from app.domain.models import (
    Component,
    Connection,
    ConsensusResult,
    Risk,
    Score,
)


class TestConsensusToResultJson:
    def test_basic_conversion(self):
        result = ConsensusResult(
            confidence=0.8,
            components=[Component(name="API", type="gateway", description="Routes", technology="NGINX")],
            connections=[Connection(source="API", target="DB", protocol="HTTP")],
            risks=[Risk(severity="high", category="security", title="No Auth", description="Missing", recommendation="Add JWT")],
            recommendations=["Add JWT"],
            scores=Score(scalability=7, security=6, reliability=8, maintainability=7, overall=7),
            providers_used=["openai"],
            processing_time_ms=1234,
        )

        raw = _consensus_to_result_json(result)
        data = json.loads(raw)

        # Components should have confidence and no technology
        comp = data["components"][0]
        assert comp["confidence"] == 0.8
        assert "technology" not in comp

        # Connections should rename protocol -> type
        conn = data["connections"][0]
        assert conn["type"] == "HTTP"
        assert "protocol" not in conn

        # Risks should rename recommendation -> mitigation
        risk = data["risks"][0]
        assert risk["mitigation"] == "Add JWT"
        assert "recommendation" not in risk

        # Top-level fields should be removed
        assert "providers_used" not in data
        assert "processing_time_ms" not in data

    def test_empty_result_conversion(self):
        result = ConsensusResult(confidence=0.0)
        raw = _consensus_to_result_json(result)
        data = json.loads(raw)
        assert data["components"] == []
        assert data["risks"] == []

    def test_preserves_scores(self):
        result = ConsensusResult(
            confidence=0.5,
            scores=Score(scalability=9, security=8, reliability=7, maintainability=6, overall=7.5),
        )
        raw = _consensus_to_result_json(result)
        data = json.loads(raw)
        assert data["scores"]["scalability"] == 9
        assert data["scores"]["overall"] == 7.5
