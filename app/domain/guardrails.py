import json

import structlog

from app.domain.models import ProviderResponse, Score

logger = structlog.get_logger()

REQUIRED_FIELDS = {"components", "risks", "scores"}


def validate_provider_response(response: ProviderResponse) -> bool:
    if not response.components:
        logger.warning("Provider response has no components", provider=response.provider_name)
        return False

    if response.scores is None:
        logger.warning("Provider response has no scores", provider=response.provider_name)
        return False

    if not _scores_in_range(response.scores):
        logger.warning("Provider scores out of range", provider=response.provider_name)
        return False

    return True


def apply_cross_reference(responses: list[ProviderResponse], min_confirmations: int = 2) -> list[ProviderResponse]:
    if len(responses) < min_confirmations:
        return responses
    return [r for r in responses if validate_provider_response(r)]


def _scores_in_range(scores: Score) -> bool:
    for field in ["scalability", "security", "reliability", "maintainability", "overall"]:
        value = getattr(scores, field)
        if not (0 <= value <= 10):
            return False
    return True
