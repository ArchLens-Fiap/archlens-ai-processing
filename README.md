# :brain: ArchLens AI Processing

Multi-provider AI analysis engine with consensus voting and guardrails for architecture diagram evaluation.

## Architecture Overview

```mermaid
graph LR
    BUS{{RabbitMQ}} -->|ProcessingStartedEvent| AI[AI Processing :8000]
    AI --> REDIS[(Redis Cache)]
    AI --> OPENAI[OpenAI GPT-4o]
    AI --> GEMINI[Google Gemini 2.0]
    AI --> CLAUDE[Anthropic Claude]
    AI -->|AnalysisCompleted/FailedEvent| BUS
    style AI fill:#FF5722,stroke:#333,color:#fff
```

## Consensus Engine

```mermaid
graph TD
    IMG[Diagram Image] --> P1[GPT-4o]
    IMG --> P2[GPT-4o Mini]
    IMG --> P3[Gemini 2.0 Flash]
    IMG --> P4[Claude Sonnet]
    P1 & P2 & P3 & P4 --> CE[Consensus Engine]
    CE -->|Levenshtein >= 65%| RESULT[Final Analysis]
```

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI | HTTP framework |
| Hexagonal Architecture | Project structure |
| Redis | Cache by file hash |
| Levenshtein matching | Fuzzy consensus (65% threshold) |
| Guardrails | Input/output validation |

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health` | No | Health check |
| `POST` | `/api/analyze` | Yes | Submit diagram for AI analysis |
| `POST` | `/api/chat` | Yes | Chat about an analysis |

## AI Providers

| Provider | Model |
|---|---|
| OpenAI | GPT-4o, GPT-4o Mini |
| Google | Gemini 2.0 Flash |
| Anthropic | Claude Sonnet |

## Running

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The service starts on **port 8000**.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `GOOGLE_API_KEY` | Google Gemini API key | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `RABBITMQ_HOST` | RabbitMQ host | `localhost` |

## Events

- **Consumes:** `ProcessingStartedEvent`
- **Publishes:** `AnalysisCompletedEvent`, `AnalysisFailedEvent`
