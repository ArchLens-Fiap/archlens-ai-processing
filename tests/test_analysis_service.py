import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.analysis_service import AnalysisService
from app.domain.models import (
    Component,
    Connection,
    ConsensusResult,
    ProviderResponse,
    Risk,
    Score,
)


def _make_provider(name: str = "mock-provider", weight: float = 1.0):
    provider = AsyncMock()
    provider.name = name
    provider.weight = weight
    return provider


def _make_valid_response(provider_name: str = "mock") -> ProviderResponse:
    return ProviderResponse(
        provider_name=provider_name,
        components=[Component(name="API Gateway", type="gateway", description="Routes traffic")],
        connections=[Connection(source="API Gateway", target="Service A", protocol="HTTP")],
        risks=[Risk(severity="medium", category="security", title="No TLS", description="No encryption", recommendation="Add TLS")],
        recommendations=["Add TLS"],
        scores=Score(scalability=7, security=6, reliability=8, maintainability=7, overall=7),
    )


class TestAnalysisServiceProperties:
    def test_has_providers_true(self):
        registry = MagicMock()
        registry.providers = [_make_provider()]
        service = AnalysisService(registry)
        assert service.has_providers is True

    def test_has_providers_false(self):
        registry = MagicMock()
        registry.providers = []
        service = AnalysisService(registry)
        assert service.has_providers is False

    def test_first_provider_returns_provider(self):
        p = _make_provider("openai")
        registry = MagicMock()
        registry.providers = [p]
        service = AnalysisService(registry)
        assert service.first_provider == p

    def test_first_provider_returns_none_when_empty(self):
        registry = MagicMock()
        registry.providers = []
        service = AnalysisService(registry)
        assert service.first_provider is None


class TestAnalysisServiceAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_no_providers_returns_zero_confidence(self, sample_image_bytes):
        registry = MagicMock()
        registry.providers = []
        service = AnalysisService(registry)
        result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence == 0.0
        assert result.components == []

    @pytest.mark.asyncio
    async def test_analyze_single_provider_success(self, sample_image_bytes):
        provider = _make_provider("openai")
        provider.analyze_diagram.return_value = _make_valid_response("openai")
        registry = MagicMock()
        registry.providers = [provider]
        service = AnalysisService(registry)

        result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence > 0
        assert "openai" in result.providers_used
        assert len(result.components) == 1
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_analyze_multiple_providers(self, sample_image_bytes):
        p1 = _make_provider("openai")
        p1.analyze_diagram.return_value = _make_valid_response("openai")
        p2 = _make_provider("gemini")
        p2.analyze_diagram.return_value = _make_valid_response("gemini")

        registry = MagicMock()
        registry.providers = [p1, p2]
        service = AnalysisService(registry)

        result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence > 0
        assert len(result.providers_used) == 2

    @pytest.mark.asyncio
    async def test_analyze_provider_raises_exception(self, sample_image_bytes):
        provider = _make_provider("openai")
        provider.analyze_diagram.side_effect = Exception("API error")
        registry = MagicMock()
        registry.providers = [provider]
        service = AnalysisService(registry)

        result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_provider_timeout(self, sample_image_bytes):
        provider = _make_provider("slow")

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(999)

        provider.analyze_diagram.side_effect = slow_call
        registry = MagicMock()
        registry.providers = [provider]
        service = AnalysisService(registry)

        # Patch timeout to be very short
        with patch("app.domain.analysis_service.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_one_provider_fails_other_succeeds(self, sample_image_bytes):
        p_good = _make_provider("openai")
        p_good.analyze_diagram.return_value = _make_valid_response("openai")

        p_bad = _make_provider("gemini")
        p_bad.analyze_diagram.side_effect = Exception("Provider failure")

        registry = MagicMock()
        registry.providers = [p_good, p_bad]
        service = AnalysisService(registry)

        result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence > 0
        assert "openai" in result.providers_used

    @pytest.mark.asyncio
    async def test_analyze_invalid_response_filtered(self, sample_image_bytes):
        provider = _make_provider("openai")
        # Return response with no components (invalid)
        provider.analyze_diagram.return_value = ProviderResponse(
            provider_name="openai",
            components=[],
            scores=Score(scalability=5, security=5, reliability=5, maintainability=5, overall=5),
        )
        registry = MagicMock()
        registry.providers = [provider]
        service = AnalysisService(registry)

        result = await service.analyze(sample_image_bytes, "diagram.png")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_pdf_file(self, sample_image_bytes):
        provider = _make_provider("openai")
        provider.analyze_diagram.return_value = _make_valid_response("openai")
        registry = MagicMock()
        registry.providers = [provider]
        service = AnalysisService(registry)

        with patch("app.domain.analysis_service.convert_pdf_to_images", return_value=[sample_image_bytes]):
            result = await service.analyze(b"fake-pdf-data", "architecture.pdf")
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_analyze_pdf_no_pages_fallback(self, sample_image_bytes):
        provider = _make_provider("openai")
        provider.analyze_diagram.return_value = _make_valid_response("openai")
        registry = MagicMock()
        registry.providers = [provider]
        service = AnalysisService(registry)

        with patch("app.domain.analysis_service.convert_pdf_to_images", return_value=[]):
            result = await service.analyze(b"fake-pdf-data", "architecture.pdf")
        # Should still proceed (uses raw bytes as fallback)
        assert isinstance(result, ConsensusResult)


class TestSafeAnalyze:
    @pytest.mark.asyncio
    async def test_safe_analyze_returns_none_on_timeout(self, sample_image_bytes):
        provider = _make_provider("slow")
        provider.analyze_diagram.side_effect = asyncio.TimeoutError()

        registry = MagicMock()
        registry.providers = []
        service = AnalysisService(registry)

        result = await service._safe_analyze(provider, sample_image_bytes, "test.png")
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_analyze_returns_none_on_exception(self, sample_image_bytes):
        provider = _make_provider("broken")
        provider.analyze_diagram.side_effect = RuntimeError("crash")

        registry = MagicMock()
        registry.providers = []
        service = AnalysisService(registry)

        result = await service._safe_analyze(provider, sample_image_bytes, "test.png")
        assert result is None

    @pytest.mark.asyncio
    async def test_safe_analyze_returns_response_on_success(self, sample_image_bytes):
        provider = _make_provider("openai")
        expected = _make_valid_response("openai")
        provider.analyze_diagram.return_value = expected

        registry = MagicMock()
        registry.providers = []
        service = AnalysisService(registry)

        result = await service._safe_analyze(provider, sample_image_bytes, "test.png")
        assert result is not None
        assert result.provider_name == "openai"
