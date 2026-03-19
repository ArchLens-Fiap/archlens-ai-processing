"""Redis-based vector store for RAG retrieval using OpenAI embeddings."""

import json
import hashlib

import numpy as np
import structlog
from openai import AsyncOpenAI
import redis.asyncio as aioredis

from app.config import get_settings
from app.domain.embeddings import chunk_analysis

logger = structlog.get_logger()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
INDEX_PREFIX = "rag:"
TTL = 86400  # 24 hours


class VectorStore:

    def __init__(self):
        settings = get_settings()
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        self._openai: AsyncOpenAI | None = None
        if settings.openai_api_key:
            kwargs = {"base_url": settings.openai_base_url} if settings.openai_base_url else {}
            self._openai = AsyncOpenAI(api_key=settings.openai_api_key, **kwargs)

    @property
    def available(self) -> bool:
        return self._openai is not None

    async def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts using OpenAI."""
        response = await self._openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def index_analysis(self, analysis_id: str, result: dict) -> int:
        """Chunk an analysis result, embed it, and store in Redis.

        Returns the number of chunks indexed.
        """
        if not self.available:
            return 0

        chunks = chunk_analysis(result)
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        try:
            embeddings = await self._get_embeddings(texts)
        except Exception as e:
            logger.warning("Failed to generate embeddings, skipping RAG indexing", error=str(e))
            return 0

        pipe = await self._redis.pipeline()
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            key = f"{INDEX_PREFIX}{analysis_id}:{i}"
            blob = np.array(embedding, dtype=np.float32).tobytes()
            pipe.hset(key, mapping={
                b"text": chunk["text"].encode(),
                b"section": chunk["section"].encode(),
                b"embedding": blob,
            })
            pipe.expire(key, TTL)

        await pipe.execute()
        logger.info("Indexed analysis for RAG", analysis_id=analysis_id, chunks=len(chunks))
        return len(chunks)

    async def search(self, analysis_id: str, query: str, top_k: int = 5) -> list[str]:
        """Search for the most relevant chunks for a query using cosine similarity.

        Falls back to empty list if embeddings are unavailable.
        """
        if not self.available:
            return []

        try:
            query_embedding = (await self._get_embeddings([query]))[0]
        except Exception as e:
            logger.warning("Failed to embed query", error=str(e))
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)

        # Scan for all chunks of this analysis
        pattern = f"{INDEX_PREFIX}{analysis_id}:*"
        scored: list[tuple[float, str]] = []

        async for key in self._redis.scan_iter(match=pattern.encode()):
            data = await self._redis.hgetall(key)
            if b"embedding" not in data or b"text" not in data:
                continue
            stored_vec = np.frombuffer(data[b"embedding"], dtype=np.float32)
            # Cosine similarity
            similarity = float(np.dot(query_vec, stored_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(stored_vec) + 1e-10))
            scored.append((similarity, data[b"text"].decode()))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [text for _, text in scored[:top_k]]
        logger.info("RAG search", analysis_id=analysis_id, query_len=len(query), results=len(results))
        return results

    async def close(self) -> None:
        await self._redis.aclose()
