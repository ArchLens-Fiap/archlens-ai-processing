import json

import aio_pika
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.adapters.provider_registry import ProviderRegistry
from app.config import get_settings
from app.domain.analysis_service import AnalysisService
from app.domain.models import ConsensusResult
from app.domain.preprocessing import compute_file_hash
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.storage import MinioStorage
from app.infrastructure.vector_store import VectorStore
from app.messaging.publisher import MassTransitPublisher

logger = structlog.get_logger()

EXCHANGE_NAME = "ArchLens.Contracts.Events:ProcessingStartedEvent"
QUEUE_NAME = "ai-processing-service"


def _consensus_to_result_json(result: ConsensusResult) -> str:
    data = result.model_dump()

    for comp in data.get("components", []):
        comp["confidence"] = data.get("confidence", 0.0)
        comp.pop("technology", None)

    for conn in data.get("connections", []):
        conn["type"] = conn.pop("protocol", "")

    for risk in data.get("risks", []):
        risk["mitigation"] = risk.pop("recommendation", "")

    data.pop("providers_used", None)
    data.pop("processing_time_ms", None)

    return json.dumps(data)


async def start_consumer() -> aio_pika.abc.AbstractRobustConnection:
    settings = get_settings()

    registry = ProviderRegistry()
    analysis_service = AnalysisService(registry)
    storage = MinioStorage()
    cache = AnalysisCache()
    vector_store = VectorStore()

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    publisher = MassTransitPublisher(connection)

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.FANOUT, durable=True
    )
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange)

    async def on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        async with message.process():
            envelope = json.loads(message.body.decode())
            body = envelope.get("message", envelope)

            analysis_id = body.get("analysisId", "")
            diagram_id = body.get("diagramId", "")
            storage_path = body.get("storagePath", "")

            log = logger.bind(analysis_id=analysis_id, diagram_id=diagram_id)
            log.info("Received ProcessingStartedEvent", storage_path=storage_path)

            try:
                file_bytes = await storage.download(storage_path)
                file_hash = compute_file_hash(file_bytes)

                cached = await cache.get(file_hash)
                if cached:
                    log.info("Using cached result", file_hash=file_hash)
                    result = ConsensusResult(**cached)
                else:
                    result = await _analyze_with_retry(analysis_service, file_bytes, storage_path)
                    await cache.set(file_hash, result.model_dump())

                result_json = _consensus_to_result_json(result)
                await cache.set_by_analysis(analysis_id, result.model_dump())
                await vector_store.index_analysis(analysis_id, result.model_dump())

                await publisher.publish_analysis_completed(
                    analysis_id=analysis_id,
                    diagram_id=diagram_id,
                    result_json=result_json,
                    providers_used=result.providers_used,
                    processing_time_ms=result.processing_time_ms,
                )

                log.info(
                    "Analysis pipeline completed",
                    providers=result.providers_used,
                    confidence=result.confidence,
                    elapsed_ms=result.processing_time_ms,
                )

            except Exception as exc:
                log.error("Analysis pipeline failed", error=str(exc))
                await publisher.publish_analysis_failed(
                    analysis_id=analysis_id,
                    diagram_id=diagram_id,
                    error_message=str(exc),
                    failed_providers=[p.name for p in registry.providers],
                )

    await queue.consume(on_message)
    logger.info("RabbitMQ consumer started", queue=QUEUE_NAME, exchange=EXCHANGE_NAME)

    return connection


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10), reraise=True)
async def _analyze_with_retry(
    service: AnalysisService, file_bytes: bytes, file_name: str
) -> ConsensusResult:
    return await service.analyze(file_bytes, file_name)
