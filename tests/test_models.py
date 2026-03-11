import pytest
from pydantic import ValidationError

from app.domain.models import Component, Connection, ConsensusResult, Risk, Score


class TestScore:
    def test_valid_score(self):
        score = Score(scalability=7.5, security=8.0, reliability=6.5, maintainability=7.0, overall=7.25)
        assert score.scalability == 7.5
        assert score.overall == 7.25

    def test_score_below_zero_should_fail(self):
        with pytest.raises(ValidationError):
            Score(scalability=-1, security=8, reliability=6, maintainability=7, overall=5)

    def test_score_above_ten_should_fail(self):
        with pytest.raises(ValidationError):
            Score(scalability=11, security=8, reliability=6, maintainability=7, overall=5)


class TestComponent:
    def test_valid_component(self):
        comp = Component(name="API Gateway", type="gateway", description="Routes traffic")
        assert comp.name == "API Gateway"
        assert comp.type == "gateway"

    def test_component_defaults(self):
        comp = Component(name="Test", type="service")
        assert comp.description == ""
        assert comp.technology == ""


class TestRisk:
    def test_valid_risk(self):
        risk = Risk(
            severity="high", category="security",
            title="No Auth", description="Missing auth",
            recommendation="Add JWT",
        )
        assert risk.severity == "high"
        assert risk.recommendation == "Add JWT"


class TestConnection:
    def test_valid_connection(self):
        conn = Connection(source="A", target="B", protocol="HTTP")
        assert conn.source == "A"
        assert conn.target == "B"


class TestConsensusResult:
    def test_empty_result(self):
        result = ConsensusResult(confidence=0.0)
        assert result.components == []
        assert result.confidence == 0.0
        assert result.processing_time_ms == 0

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError):
            ConsensusResult(confidence=1.5)

        with pytest.raises(ValidationError):
            ConsensusResult(confidence=-0.1)
