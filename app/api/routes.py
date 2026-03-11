import json

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from app.adapters.provider_registry import ProviderRegistry
from app.domain.analysis_service import AnalysisService
from app.domain.models import ConsensusResult

router = APIRouter()

_registry = None
_analysis_service = None


def get_analysis_service() -> AnalysisService:
    global _registry, _analysis_service
    if _analysis_service is None:
        _registry = ProviderRegistry()
        _analysis_service = AnalysisService(_registry)
    return _analysis_service


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


@router.post("/chat")
async def chat_followup(
    analysis_id: str,
    question: str,
):
    service = get_analysis_service()
    if not service.has_providers:
        raise HTTPException(status_code=503, detail="No AI providers available")

    provider = service.first_provider

    async def generate():
        response = await provider.chat(
            context=f"Analysis ID: {analysis_id}",
            question=question,
            history=[],
        )
        yield f"data: {json.dumps({'content': response})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
