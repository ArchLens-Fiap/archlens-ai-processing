"""Chunking and embedding generation for RAG-based chat context."""

import structlog

from app.domain.models import ConsensusResult

logger = structlog.get_logger()


def chunk_analysis(result: dict) -> list[dict]:
    """Split an analysis result into semantic chunks for embedding.

    Each chunk has a 'text' (content) and 'section' (metadata) field.
    """
    chunks: list[dict] = []

    for comp in result.get("components", []):
        text = f"Component: {comp.get('name', '?')} (type: {comp.get('type', '?')}). {comp.get('description', '')}".strip()
        if comp.get("technology"):
            text += f" Technology: {comp['technology']}."
        chunks.append({"section": "component", "text": text})

    for conn in result.get("connections", []):
        text = f"Connection: {conn.get('source', '?')} -> {conn.get('target', '?')} via {conn.get('protocol', '?')}. {conn.get('description', '')}".strip()
        chunks.append({"section": "connection", "text": text})

    for risk in result.get("risks", []):
        text = (
            f"Risk [{risk.get('severity', '?')}] ({risk.get('category', '?')}): {risk.get('title', '?')}. "
            f"{risk.get('description', '')} Recommendation: {risk.get('recommendation', '')}"
        ).strip()
        chunks.append({"section": "risk", "text": text})

    for rec in result.get("recommendations", []):
        chunks.append({"section": "recommendation", "text": f"Recommendation: {rec}"})

    scores = result.get("scores")
    if scores:
        text = (
            f"Architecture Scores: scalability={scores.get('scalability')}/10, "
            f"security={scores.get('security')}/10, reliability={scores.get('reliability')}/10, "
            f"maintainability={scores.get('maintainability')}/10, overall={scores.get('overall')}/10."
        )
        chunks.append({"section": "scores", "text": text})

    confidence = result.get("confidence")
    providers = result.get("providers_used", [])
    if confidence is not None:
        text = f"Analysis confidence: {confidence:.0%}. Providers used: {', '.join(providers)}."
        chunks.append({"section": "metadata", "text": text})

    logger.info("Chunked analysis", total_chunks=len(chunks))
    return chunks
