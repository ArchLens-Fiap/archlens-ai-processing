from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import get_settings
from app.messaging.consumer import start_consumer

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

    return app


app = create_app()
