import asyncio
import json
import re

import structlog
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.adapters.provider_registry import ProviderRegistry
from app.domain.analysis_service import AnalysisService
from app.domain.models import ConsensusResult
from app.infrastructure.cache import AnalysisCache
from app.infrastructure.vector_store import VectorStore
from app.prompts.loader import load_prompt

logger = structlog.get_logger()

router = APIRouter()

_registry = None
_analysis_service = None
_cache = None
_vector_store = None


def get_analysis_service() -> AnalysisService:
    global _registry, _analysis_service
    if _analysis_service is None:
        _registry = ProviderRegistry()
        _analysis_service = AnalysisService(_registry)
    return _analysis_service


def get_cache() -> AnalysisCache:
    global _cache
    if _cache is None:
        _cache = AnalysisCache()
    return _cache


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-processing"}


@router.post("/analyze", response_model=ConsensusResult)
async def analyze_diagram(file: UploadFile = File(...)):
    if file.content_type not in ("image/png", "image/jpeg", "image/webp", "application/pdf"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    service = get_analysis_service()
    result = await service.analyze(file_bytes, file.filename or "diagram.png")

    return result


def _build_context(data: dict, diagram_name: str | None = None) -> str:
    parts = []

    if diagram_name:
        parts.append(f"Diagram: {diagram_name}")

    components = data.get("components", [])
    if components:
        comp_lines = [f"- {c.get('name', '?')} ({c.get('type', '?')}): {c.get('description', '')[:120]}" for c in components[:20]]
        parts.append(f"Components ({len(components)}):\n" + "\n".join(comp_lines))

    connections = data.get("connections", [])
    if connections:
        conn_lines = [f"- {c.get('source', '?')} -> {c.get('target', '?')} ({c.get('type', '?')}): {c.get('description', '')[:80]}" for c in connections[:15]]
        parts.append(f"Connections ({len(connections)}):\n" + "\n".join(conn_lines))

    risks = data.get("risks", [])
    if risks:
        risk_lines = [f"- [{r.get('severity', '?')}] {r.get('title', '?')}: {r.get('description', '')[:100]}" for r in risks[:10]]
        parts.append(f"Risks ({len(risks)}):\n" + "\n".join(risk_lines))

    recs = data.get("recommendations", [])
    if recs:
        parts.append(f"Recommendations: {'; '.join(recs[:10])}")

    scores = data.get("scores")
    if scores:
        parts.append(f"Scores: scalability={scores.get('scalability')}, security={scores.get('security')}, reliability={scores.get('reliability')}, maintainability={scores.get('maintainability')}, overall={scores.get('overall')}")

    confidence = data.get("confidence")
    if confidence is not None:
        parts.append(f"Confidence: {confidence}")

    providers = data.get("providers_used", [])
    if providers:
        parts.append(f"Providers used: {', '.join(providers)}")

    return "\n\n".join(parts) if parts else "No analysis data available."


class ChatRequest(BaseModel):
    analysis_id: str
    question: str
    history: list[dict] = []
    diagram_name: str | None = None


@router.post("/chat")
async def chat_followup(
    request: ChatRequest | None = None,
    analysis_id: str | None = None,
    question: str | None = None,
):
    aid = request.analysis_id if request else analysis_id
    q = request.question if request else question
    hist = request.history if request else []
    dname = request.diagram_name if request else None

    if not aid or not q:
        raise HTTPException(status_code=400, detail="analysis_id and question are required")

    service = get_analysis_service()
    if not service.has_providers:
        raise HTTPException(status_code=503, detail="No AI providers available")

    # RAG: retrieve relevant chunks via vector similarity, fallback to full context
    vs = get_vector_store()
    rag_chunks = await vs.search(aid, q, top_k=5) if vs.available else []

    if rag_chunks:
        prefix = f"Diagram: {dname}\n\n" if dname else ""
        context = prefix + "Relevant analysis context:\n\n" + "\n\n".join(rag_chunks)
        logger.info("Using RAG context", analysis_id=aid, chunks=len(rag_chunks))
    else:
        cache = get_cache()
        cached_result = await cache.get_by_analysis(aid)
        context = _build_context(cached_result, dname) if cached_result else f"Analysis ID: {aid} (no cached data available)"

    providers = service.chat_provider_chain

    return StreamingResponse(
        _chat_with_fallback(providers, context, q, hist),
        media_type="text/event-stream",
    )


_TIER_TIMEOUTS = [8.0, 10.0, 15.0]


async def _try_chat_provider(provider, context: str, question: str, history: list[dict], tier_timeout: float) -> str | None:
    """Try a single provider with a timeout. Returns the response or None on failure."""
    try:
        logger.info("Chat trying provider", provider=provider.name, timeout=tier_timeout)
        async with asyncio.timeout(tier_timeout):
            response = await provider.chat(context=context, question=question, history=history)
        logger.info("Chat response from provider", provider=provider.name)
        return response
    except TimeoutError:
        logger.warning("Chat provider timed out", provider=provider.name)
        return None
    except Exception as e:
        logger.warning("Chat provider failed", provider=provider.name, error=str(e))
        return None


async def _chat_with_fallback(providers: list, context: str, question: str, history: list[dict]):
    """Tiered fallback: try each provider with increasing timeouts."""
    for i, provider in enumerate(providers):
        timeout = _TIER_TIMEOUTS[i] if i < len(_TIER_TIMEOUTS) else _TIER_TIMEOUTS[-1]
        response = await _try_chat_provider(provider, context, question, history, timeout)
        if response is not None:
            yield f"data: {json.dumps({'content': response})}\n\n"
            yield "data: [DONE]\n\n"
            return

    yield f"data: {json.dumps({'content': 'All AI providers are currently slow or unavailable. Please try again in a moment.'})}\n\n"
    yield "data: [DONE]\n\n"


def _fix_mermaid_syntax(code: str) -> str:
    """Fix common Mermaid syntax issues produced by LLMs."""
    lines = []
    for line in code.split("\n"):
        # Fix labels with parentheses not wrapped in quotes: A[Text (stuff)] -> A["Text (stuff)"]
        line = re.sub(
            r'(\w+)\[([^\]"]*\([^\]]*\))\]',
            r'\1["\2"]',
            line,
        )
        # Remove classDef and ::: style references (unsupported in strict mode)
        if line.strip().startswith("classDef ") or line.strip().startswith("style "):
            continue
        line = re.sub(r':::\w+', '', line)
        lines.append(line)
    return "\n".join(lines)


class FixDiagramRequest(BaseModel):
    analysis_id: str
    diagram_name: str | None = None


@router.post("/generate-fixed-diagram")
async def generate_fixed_diagram(request: FixDiagramRequest):
    service = get_analysis_service()
    if not service.has_providers:
        raise HTTPException(status_code=503, detail="No AI providers available")

    cache = get_cache()
    cached_result = await cache.get_by_analysis(request.analysis_id)
    if not cached_result:
        raise HTTPException(status_code=404, detail="Analysis not found in cache. Please re-analyze the diagram.")

    context = _build_context(cached_result, request.diagram_name)
    fix_prompt = load_prompt("fix-diagram")
    question = f"{fix_prompt}\n\nAnalysis results:\n{context}"

    providers = service.chat_provider_chain
    for i, provider in enumerate(providers):
        timeout = 30.0 if i == 0 else 45.0
        try:
            logger.info("Generating fixed diagram", provider=provider.name)
            async with asyncio.timeout(timeout):
                mermaid_code = await provider.chat(context="", question=question, history=[])
            # Clean up response - extract only mermaid code
            mermaid_code = mermaid_code.strip()
            if "```mermaid" in mermaid_code:
                mermaid_code = mermaid_code.split("```mermaid")[1].split("```")[0].strip()
            elif "```" in mermaid_code:
                mermaid_code = mermaid_code.split("```")[1].split("```")[0].strip()

            # Fix common Mermaid syntax issues from LLMs
            mermaid_code = _fix_mermaid_syntax(mermaid_code)

            logger.info("Fixed diagram generated", provider=provider.name, length=len(mermaid_code))
            return {"mermaid": mermaid_code, "provider": provider.name}
        except Exception as e:
            logger.warning("Fix diagram provider failed", provider=provider.name, error=str(e))
            continue

    raise HTTPException(status_code=503, detail="All providers failed to generate the fixed diagram")
