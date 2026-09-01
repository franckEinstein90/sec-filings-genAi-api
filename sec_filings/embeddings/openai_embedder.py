from __future__ import annotations

from openai import OpenAI

from sec_filings.config import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL
from sec_filings.embeddings.base import Embedder

_BATCH = 64


class OpenAIEmbedder(Embedder):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model_name = model or OPENAI_EMBEDDING_MODEL
        self._client = OpenAI(api_key=api_key or OPENAI_API_KEY)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH):
            batch = texts[start : start + _BATCH]
            response = self._client.embeddings.create(model=self.model_name, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        return vectors
