from abc import ABC, abstractmethod

from app.domain.models import ProviderResponse


class AIProviderPort(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def weight(self) -> float:
        ...

    @abstractmethod
    async def analyze_diagram(self, image_bytes: bytes, file_name: str) -> ProviderResponse:
        ...

    @abstractmethod
    async def chat(self, context: str, question: str, history: list[dict]) -> str:
        ...
