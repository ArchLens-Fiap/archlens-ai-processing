import pytest

from app.domain.models import (
    Component,
    Connection,
    ConsensusResult,
    ProviderResponse,
    Risk,
    Score,
)


@pytest.fixture
def sample_score():
    return Score(
        scalability=7.5,
        security=8.0,
        reliability=6.5,
        maintainability=7.0,
        overall=7.25,
    )


@pytest.fixture
def sample_component():
    return Component(
        name="API Gateway",
        type="gateway",
        description="Routes traffic to microservices",
        technology="NGINX",
    )


@pytest.fixture
def sample_risk():
    return Risk(
        severity="high",
        category="reliability",
        title="Single Point of Failure",
        description="The API gateway has no redundancy",
        recommendation="Add a second gateway instance with load balancer",
    )


@pytest.fixture
def sample_connection():
    return Connection(
        source="API Gateway",
        target="User Service",
        protocol="HTTP/REST",
        description="Forwards user requests",
    )


@pytest.fixture
def sample_provider_response(sample_component, sample_risk, sample_connection, sample_score):
    return ProviderResponse(
        provider_name="openai",
        components=[
            sample_component,
            Component(name="User Service", type="microservice", description="Handles user operations"),
            Component(name="PostgreSQL", type="database", description="Primary data store"),
        ],
        connections=[sample_connection],
        risks=[sample_risk],
        recommendations=["Add circuit breaker pattern", "Implement retry logic"],
        scores=sample_score,
    )


@pytest.fixture
def two_provider_responses(sample_score):
    openai_response = ProviderResponse(
        provider_name="openai",
        components=[
            Component(name="API Gateway", type="gateway", description="Routes traffic"),
            Component(name="User Service", type="microservice", description="Handles users"),
            Component(name="PostgreSQL", type="database", description="Main DB"),
        ],
        connections=[
            Connection(source="API Gateway", target="User Service", protocol="HTTP"),
        ],
        risks=[
            Risk(severity="high", category="reliability", title="Single Point of Failure",
                 description="No redundancy on gateway", recommendation="Add failover"),
        ],
        recommendations=["Add circuit breaker"],
        scores=Score(scalability=7.0, security=8.0, reliability=6.0, maintainability=7.0, overall=7.0),
    )

    gemini_response = ProviderResponse(
        provider_name="gemini",
        components=[
            Component(name="API Gateway", type="gateway", description="Entry point for all requests"),
            Component(name="Users Service", type="microservice", description="User management"),
            Component(name="PostgreSQL", type="database", description="Relational database"),
            Component(name="Redis", type="cache", description="In-memory cache"),
        ],
        connections=[
            Connection(source="API Gateway", target="Users Service", protocol="REST"),
            Connection(source="Users Service", target="Redis", protocol="TCP"),
        ],
        risks=[
            Risk(severity="high", category="reliability", title="SPOF in Gateway",
                 description="Gateway has no failover mechanism", recommendation="Deploy multiple instances"),
            Risk(severity="medium", category="security", title="No Rate Limiting",
                 description="API has no rate limiting", recommendation="Add rate limiter"),
        ],
        recommendations=["Add circuit breaker pattern", "Implement rate limiting"],
        scores=Score(scalability=8.0, security=7.0, reliability=7.0, maintainability=8.0, overall=7.5),
    )

    return [openai_response, gemini_response]


@pytest.fixture
def sample_image_bytes():
    from PIL import Image
    import io
    img = Image.new("RGB", (100, 100), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def large_image_bytes():
    from PIL import Image
    import io
    img = Image.new("RGB", (4096, 3072), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def rgba_image_bytes():
    from PIL import Image
    import io
    img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
