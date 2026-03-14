from pydantic import BaseModel, Field


class Component(BaseModel):
    name: str
    type: str = Field(description="e.g. microservice, database, queue, load_balancer, gateway, cache")
    description: str = ""
    technology: str = ""


class Connection(BaseModel):
    source: str
    target: str
    protocol: str = ""
    description: str = ""


class Risk(BaseModel):
    severity: str = Field(description="critical, high, medium, low")
    category: str = Field(description="e.g. scalability, security, reliability, maintainability")
    title: str
    description: str
    recommendation: str


class Score(BaseModel):
    scalability: float = Field(ge=0, le=10)
    security: float = Field(ge=0, le=10)
    reliability: float = Field(ge=0, le=10)
    maintainability: float = Field(ge=0, le=10)
    overall: float = Field(ge=0, le=10)


class ProviderResponse(BaseModel):
    provider_name: str = ""
    provider_weight: float = 1.0
    components: list[Component] = []
    connections: list[Connection] = []
    risks: list[Risk] = []
    recommendations: list[str] = []
    scores: Score | None = None
    raw_response: str = ""


class ConsensusResult(BaseModel):
    components: list[Component] = []
    connections: list[Connection] = []
    risks: list[Risk] = []
    recommendations: list[str] = []
    scores: Score | None = None
    providers_used: list[str] = []
    confidence: float = Field(ge=0, le=1, description="Overall confidence from consensus")
    processing_time_ms: int = 0
