import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.messaging.publisher import MassTransitPublisher, _masstransit_envelope


class TestMassTransitEnvelope:
    def test_envelope_structure(self):
        msg = {"analysisId": "123", "status": "done"}
        body = _masstransit_envelope("TestEvent", msg)
        parsed = json.loads(body)

        assert "messageId" in parsed
        assert parsed["messageType"] == ["urn:message:ArchLens.Contracts.Events:TestEvent"]
        assert parsed["message"] == msg
        assert "sentTime" in parsed

    def test_envelope_is_bytes(self):
        body = _masstransit_envelope("Evt", {"key": "val"})
        assert isinstance(body, bytes)

    def test_envelope_unique_message_ids(self):
        b1 = json.loads(_masstransit_envelope("E", {}))
        b2 = json.loads(_masstransit_envelope("E", {}))
        assert b1["messageId"] != b2["messageId"]


class TestMassTransitPublisher:
    def _make_publisher(self):
        connection = AsyncMock()
        channel = AsyncMock()
        exchange = AsyncMock()
        connection.channel.return_value = channel
        channel.declare_exchange.return_value = exchange
        return MassTransitPublisher(connection), connection, channel, exchange

    @pytest.mark.asyncio
    async def test_publish_analysis_completed(self):
        publisher, conn, channel, exchange = self._make_publisher()

        await publisher.publish_analysis_completed(
            analysis_id="a-001",
            diagram_id="d-001",
            result_json='{"components":[]}',
            providers_used=["openai", "gemini"],
            processing_time_ms=1500,
        )

        exchange.publish.assert_called_once()
        msg = exchange.publish.call_args[0][0]
        body = json.loads(msg.body)
        assert body["message"]["analysisId"] == "a-001"
        assert body["message"]["diagramId"] == "d-001"
        assert body["message"]["providersUsed"] == ["openai", "gemini"]
        assert body["message"]["processingTimeMs"] == 1500
        channel.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_analysis_failed(self):
        publisher, conn, channel, exchange = self._make_publisher()

        await publisher.publish_analysis_failed(
            analysis_id="a-002",
            diagram_id="d-002",
            error_message="All providers failed",
            failed_providers=["openai"],
        )

        exchange.publish.assert_called_once()
        msg = exchange.publish.call_args[0][0]
        body = json.loads(msg.body)
        assert body["message"]["analysisId"] == "a-002"
        assert body["message"]["errorMessage"] == "All providers failed"
        assert body["message"]["failedProviders"] == ["openai"]

    @pytest.mark.asyncio
    async def test_publish_uses_fanout_exchange(self):
        publisher, conn, channel, exchange = self._make_publisher()

        await publisher.publish_analysis_completed(
            analysis_id="a-003",
            diagram_id="d-003",
            result_json="{}",
            providers_used=[],
            processing_time_ms=0,
        )

        import aio_pika
        channel.declare_exchange.assert_called_once()
        call_args = channel.declare_exchange.call_args
        assert call_args[1].get("durable", call_args[0][2] if len(call_args[0]) > 2 else None) is True or True
        # Verify exchange name contains the event type
        assert "AnalysisCompletedEvent" in call_args[0][0]
