import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import ConsensusResult, Score, Component
from app.messaging.consumer import _consensus_to_result_json, _analyze_with_retry


class TestAnalyzeWithRetry:
    @pytest.mark.asyncio
    async def test_analyze_with_retry_success(self):
        mock_service = AsyncMock()
        expected = ConsensusResult(confidence=0.9)
        mock_service.analyze.return_value = expected

        result = await _analyze_with_retry(mock_service, b"image-data", "test.png")
        assert result.confidence == 0.9
        mock_service.analyze.assert_called_once_with(b"image-data", "test.png")

    @pytest.mark.asyncio
    async def test_analyze_with_retry_retries_on_failure(self):
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = [Exception("fail"), ConsensusResult(confidence=0.7)]

        result = await _analyze_with_retry(mock_service, b"data", "file.png")
        assert result.confidence == 0.7
        assert mock_service.analyze.call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_with_retry_raises_after_max_retries(self):
        mock_service = AsyncMock()
        mock_service.analyze.side_effect = Exception("persistent failure")

        from tenacity import RetryError
        with pytest.raises(Exception):
            await _analyze_with_retry(mock_service, b"data", "file.png")


class TestConsensusToResultJsonEdgeCases:
    def test_multiple_components_get_confidence(self):
        result = ConsensusResult(
            confidence=0.75,
            components=[
                Component(name="A", type="svc"),
                Component(name="B", type="db"),
            ],
        )
        raw = _consensus_to_result_json(result)
        data = json.loads(raw)
        assert all(c["confidence"] == 0.75 for c in data["components"])

    def test_no_scores(self):
        result = ConsensusResult(confidence=0.5, scores=None)
        raw = _consensus_to_result_json(result)
        data = json.loads(raw)
        assert data["scores"] is None
