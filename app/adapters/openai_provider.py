import json
import base64

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.domain.ports import AIProviderPort
from app.domain.models import ProviderResponse
from app.prompts.loader import load_prompt

logger = structlog.get_logger()


class OpenAIProvider(AIProviderPort):

    def __init__(self, base_url: str = "", api_key: str = "", model: str = "gpt-4o", provider_name: str = "openai", weight: float = 1.0):
        settings = get_settings()
        key = api_key or settings.openai_api_key
        url = base_url or settings.openai_base_url
        self._client = AsyncOpenAI(api_key=key, **({"base_url": url} if url else {}))
        self._model = model
        self._name = provider_name
        self._weight = weight

    @property
    def name(self) -> str:
        return self._name

    @property
    def weight(self) -> float:
        return self._weight

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def analyze_diagram(self, image_bytes: bytes, file_name: str) -> ProviderResponse:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = "image/png" if file_name.endswith(".png") else "image/jpeg"

        system_prompt = load_prompt("system")
        analysis_prompt = load_prompt("analysis")
        schema_text = load_prompt("schema")

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{analysis_prompt}\n\nRespond with JSON matching this schema:\n{schema_text}"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}", "detail": "high"}},
                    ],
                },
            ],
            max_tokens=4096,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        parsed = self._parse_response(raw)
        parsed.provider_name = self._name
        parsed.raw_response = raw
        return parsed

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def chat(self, context: str, question: str, history: list[dict]) -> str:
        chat_prompt = load_prompt("chat")

        messages = [
            {"role": "system", "content": f"{chat_prompt}\n\nContext from analysis:\n{context}"},
            *history,
            {"role": "user", "content": question},
        ]

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
        )

        return response.choices[0].message.content or ""

    @staticmethod
    def _parse_response(raw: str) -> ProviderResponse:
        try:
            data = json.loads(raw)
            return ProviderResponse.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse OpenAI response", error=str(e))
            return ProviderResponse(provider_name="openai-compatible", raw_response=raw)
