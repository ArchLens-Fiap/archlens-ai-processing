import json

import structlog
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.domain.ports import AIProviderPort
from app.domain.models import ProviderResponse
from app.prompts.loader import load_prompt

logger = structlog.get_logger()


class GeminiProvider(AIProviderPort):

    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.google_ai_api_key)
        self._model = genai.GenerativeModel("gemini-2.0-flash")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def weight(self) -> float:
        return 0.9

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def analyze_diagram(self, image_bytes: bytes, file_name: str) -> ProviderResponse:
        system_prompt = load_prompt("system")
        analysis_prompt = load_prompt("analysis")
        schema_text = load_prompt("schema")

        mime_type = "image/png" if file_name.endswith(".png") else "image/jpeg"
        image_part = {"mime_type": mime_type, "data": image_bytes}

        prompt = f"{system_prompt}\n\n{analysis_prompt}\n\nRespond ONLY with valid JSON matching this schema:\n{schema_text}"

        response = await self._model.generate_content_async(
            [prompt, image_part],
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        raw = response.text or "{}"
        parsed = self._parse_response(raw)
        parsed.provider_name = self.name
        parsed.raw_response = raw
        return parsed

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def chat(self, context: str, question: str, history: list[dict]) -> str:
        chat_prompt = load_prompt("chat")

        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in history
        )

        prompt = f"{chat_prompt}\n\nContext:\n{context}\n\nHistory:\n{history_text}\n\nUser: {question}"

        response = await self._model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=2048),
        )

        return response.text or ""

    @staticmethod
    def _parse_response(raw: str) -> ProviderResponse:
        try:
            data = json.loads(raw)
            return ProviderResponse.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse Gemini response", error=str(e))
            return ProviderResponse(provider_name="gemini", raw_response=raw)
