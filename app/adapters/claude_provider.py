import json
import base64

import structlog
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.domain.ports import AIProviderPort
from app.domain.models import ProviderResponse
from app.prompts.loader import load_prompt

logger = structlog.get_logger()


class ClaudeProvider(AIProviderPort):

    def __init__(self):
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = "claude-sonnet-4-20250514"

    @property
    def name(self) -> str:
        return "claude"

    @property
    def weight(self) -> float:
        return 1.0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def analyze_diagram(self, image_bytes: bytes, file_name: str) -> ProviderResponse:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = "image/png" if file_name.endswith(".png") else "image/jpeg"
        if file_name.endswith(".webp"):
            mime_type = "image/webp"

        system_prompt = load_prompt("system")
        analysis_prompt = load_prompt("analysis")
        schema_text = load_prompt("schema")

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": mime_type, "data": b64_image},
                        },
                        {
                            "type": "text",
                            "text": f"{analysis_prompt}\n\nRespond ONLY with valid JSON matching this schema:\n{schema_text}",
                        },
                    ],
                }
            ],
            temperature=0.2,
        )

        raw = response.content[0].text if response.content else "{}"
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

        messages = []
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": question})

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=f"{chat_prompt}\n\nContext from analysis:\n{context}",
            messages=messages,
            temperature=0.3,
        )

        return response.content[0].text if response.content else ""

    @staticmethod
    def _parse_response(raw: str) -> ProviderResponse:
        try:
            clean = raw.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            data = json.loads(clean.strip())
            return ProviderResponse.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse Claude response", error=str(e))
            return ProviderResponse(provider_name="claude", raw_response=raw)
