from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from opentelemetry import trace
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.api.routes import router as api_router
from app.config import get_settings
from app.messaging.consumer import start_consumer
from app.telemetry import setup_telemetry


def _add_otel_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _add_otel_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

_rabbitmq_connection = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rabbitmq_connection
    settings = get_settings()
    logger.info("Starting AI Processing Service", environment=settings.environment)

    try:
        _rabbitmq_connection = await start_consumer()
        logger.info("RabbitMQ consumer initialized")
    except Exception as exc:
        logger.error("Failed to start RabbitMQ consumer, running in API-only mode", error=str(exc))

    yield

    if _rabbitmq_connection and not _rabbitmq_connection.is_closed:
        await _rabbitmq_connection.close()
        logger.info("RabbitMQ connection closed")

    logger.info("AI Processing Service shut down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ArchLens AI Processing Service",
        description="Multi-provider AI analysis engine for architecture diagrams",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    setup_telemetry(app)

    return app


app = create_app()
