"""Deterministic embeddings for tests and local runs without OpenAI."""

from __future__ import annotations

import hashlib
import math

from sec_filings.config import EMBEDDING_DIMENSIONS
from sec_filings.embeddings.base import Embedder


class HashEmbedder(Embedder):
    model_name = "hash-embedder"

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS):
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        values: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
            for offset in range(0, 32, 4):
                raw = int.from_bytes(digest[offset : offset + 4], "little")
                values.append((raw / 2**32) * 2.0 - 1.0)
            counter += 1
        values = values[: self.dimensions]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]
