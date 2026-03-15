from app.domain.guardrails import apply_cross_reference, validate_provider_response
from app.domain.models import Component, ProviderResponse, Score


class TestValidateProviderResponse:
    def test_valid_response(self, sample_provider_response):
        assert validate_provider_response(sample_provider_response) is True

    def test_no_components_invalid(self):
        response = ProviderResponse(
            provider_name="test",
            components=[],
            scores=Score(scalability=5, security=5, reliability=5, maintainability=5, overall=5),
        )
        assert validate_provider_response(response) is False

    def test_no_scores_invalid(self):
        response = ProviderResponse(
            provider_name="test",
            components=[Component(name="A", type="service")],
            scores=None,
        )
        assert validate_provider_response(response) is False

    def test_scores_out_of_range_invalid(self):
        # Build a response with out-of-range scores by bypassing Pydantic validation
        score = Score.model_construct(scalability=11, security=5, reliability=5, maintainability=5, overall=5)
        response = ProviderResponse(
            provider_name="test",
            components=[Component(name="A", type="service")],
        )
        response.scores = score
        assert validate_provider_response(response) is False


class TestCrossReference:
    def test_single_response_passes_through(self, sample_provider_response):
        result = apply_cross_reference([sample_provider_response])
        assert len(result) == 1

    def test_filters_invalid_responses(self):
        valid = ProviderResponse(
            provider_name="openai",
            components=[Component(name="A", type="service")],
            scores=Score(scalability=7, security=7, reliability=7, maintainability=7, overall=7),
        )
        invalid = ProviderResponse(
            provider_name="gemini",
            components=[],
            scores=Score(scalability=7, security=7, reliability=7, maintainability=7, overall=7),
        )
        result = apply_cross_reference([valid, invalid])
        assert len(result) == 1
        assert result[0].provider_name == "openai"
