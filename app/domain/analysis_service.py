import asyncio
import time

import structlog

from app.adapters.provider_registry import ProviderRegistry
from app.domain.consensus import ConsensusEngine
from app.domain.guardrails import apply_cross_reference, validate_provider_response
from app.domain.models import ConsensusResult, ProviderResponse
from app.domain.preprocessing import compute_file_hash, convert_pdf_to_images, preprocess_image

logger = structlog.get_logger()


class AnalysisService:

    def __init__(self, registry: ProviderRegistry):
        self._registry = registry
        self._consensus = ConsensusEngine()

    @property
    def has_providers(self) -> bool:
        return len(self._registry.providers) > 0

    @property
    def first_provider(self):
        providers = self._registry.providers
        return providers[0] if providers else None

    async def analyze(self, file_bytes: bytes, file_name: str) -> ConsensusResult:
        start = time.monotonic()

        if file_name.lower().endswith(".pdf"):
            pages = convert_pdf_to_images(file_bytes)
            image_bytes = preprocess_image(pages[0]) if pages else file_bytes
        else:
            image_bytes = preprocess_image(file_bytes)

        providers = self._registry.providers
        if not providers:
            return ConsensusResult(confidence=0.0)

        tasks = [
            self._safe_analyze(provider, image_bytes, file_name)
            for provider in providers
        ]
        results = await asyncio.gather(*tasks)

        valid_responses: list[ProviderResponse] = []
        for result in results:
            if result is not None and validate_provider_response(result):
                valid_responses.append(result)

        valid_responses = apply_cross_reference(valid_responses)

        if not valid_responses:
            logger.error("All providers failed or returned invalid responses")
            return ConsensusResult(
                confidence=0.0,
                providers_used=[p.name for p in providers],
            )

        consensus = self._consensus.build_consensus(valid_responses)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        consensus.processing_time_ms = elapsed_ms

        logger.info(
            "Analysis complete",
            providers_used=consensus.providers_used,
            components_found=len(consensus.components),
            risks_found=len(consensus.risks),
            confidence=consensus.confidence,
            elapsed_ms=elapsed_ms,
        )

        return consensus

    async def _safe_analyze(self, provider, image_bytes: bytes, file_name: str) -> ProviderResponse | None:
        try:
            logger.info("Starting analysis", provider=provider.name)
            result = await asyncio.wait_for(
                provider.analyze_diagram(image_bytes, file_name),
                timeout=60.0,
            )
            logger.info("Analysis succeeded", provider=provider.name)
            return result
        except asyncio.TimeoutError:
            logger.warning("Provider timed out", provider=provider.name)
            return None
        except Exception as e:
            logger.error("Provider failed", provider=provider.name, error=str(e))
            return None
