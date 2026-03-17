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
        self._model = genai.GenerativeModel("gemini-2.5-flash-lite")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def weight(self) -> float:
        return 0.9

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=5),
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
                max_output_tokens=8192,
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
            if "scores" in data and isinstance(data["scores"], dict):
                for key in ("scalability", "security", "reliability", "maintainability", "overall"):
                    if key in data["scores"]:
                        try:
                            data["scores"][key] = float(data["scores"][key])
                        except (ValueError, TypeError):
                            data["scores"][key] = 5.0
            for risk in data.get("risks", []):
                for field in ("severity", "category", "title", "description", "recommendation"):
                    if field in risk and not isinstance(risk[field], str):
                        risk[field] = str(risk.get(field, ""))
                    elif field not in risk:
                        risk[field] = ""
            for comp in data.get("components", []):
                for field in ("name", "type", "description", "technology"):
                    if field in comp and not isinstance(comp[field], str):
                        comp[field] = str(comp.get(field, ""))
                    elif field not in comp:
                        comp[field] = ""
            for conn in data.get("connections", []):
                for field in ("source", "target", "protocol", "description"):
                    if field in conn and not isinstance(conn[field], str):
                        conn[field] = str(conn.get(field, ""))
                    elif field not in conn:
                        conn[field] = ""
            return ProviderResponse.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse Gemini response", error=str(e))
            return ProviderResponse(provider_name="gemini", raw_response=raw)
