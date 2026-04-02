import json
import uuid
from datetime import datetime, timezone

import aio_pika
import structlog
from opentelemetry.propagate import inject

from app.config import get_settings

logger = structlog.get_logger()


def _inject_trace_headers() -> dict:
    headers: dict[str, str] = {}
    inject(headers)
    return headers

MT_NS = "ArchLens.Contracts.Events"


def _masstransit_envelope(message_type: str, message: dict) -> bytes:
    envelope = {
        "messageId": str(uuid.uuid4()),
        "messageType": [f"urn:message:{MT_NS}:{message_type}"],
        "message": message,
        "sentTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    return json.dumps(envelope).encode()


class MassTransitPublisher:
    def __init__(self, connection: aio_pika.abc.AbstractRobustConnection):
        self._connection = connection

    async def publish_analysis_completed(
        self,
        analysis_id: str,
        diagram_id: str,
        result_json: str,
        providers_used: list[str],
        processing_time_ms: int,
    ) -> None:
        exchange_name = f"{MT_NS}:AnalysisCompletedEvent"

        message = {
            "analysisId": analysis_id,
            "diagramId": diagram_id,
            "resultJson": result_json,
            "providersUsed": providers_used,
            "processingTimeMs": processing_time_ms,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

        body = _masstransit_envelope("AnalysisCompletedEvent", message)
        await self._publish(exchange_name, body)

        logger.info(
            "Published AnalysisCompletedEvent",
            analysis_id=analysis_id,
            diagram_id=diagram_id,
        )

    async def publish_analysis_failed(
        self,
        analysis_id: str,
        diagram_id: str,
        error_message: str,
        failed_providers: list[str],
    ) -> None:
        exchange_name = f"{MT_NS}:AnalysisFailedEvent"

        message = {
            "analysisId": analysis_id,
            "diagramId": diagram_id,
            "errorMessage": error_message,
            "failedProviders": failed_providers,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

        body = _masstransit_envelope("AnalysisFailedEvent", message)
        await self._publish(exchange_name, body)

        logger.info(
            "Published AnalysisFailedEvent",
            analysis_id=analysis_id,
            diagram_id=diagram_id,
            error=error_message,
        )

    async def _publish(self, exchange_name: str, body: bytes) -> None:
        channel = await self._connection.channel()
        exchange = await channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        await exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/vnd.masstransit+json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers=_inject_trace_headers(),
            ),
            routing_key="",
        )
        await channel.close()
