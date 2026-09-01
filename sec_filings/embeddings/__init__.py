from __future__ import annotations

import os

from sec_filings.embeddings.base import Embedder
from sec_filings.embeddings.hash_embedder import HashEmbedder
from sec_filings.embeddings.openai_embedder import OpenAIEmbedder


def get_embedder() -> Embedder:
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if provider == "hash":
        return HashEmbedder()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Provide a key or set EMBEDDING_PROVIDER=hash."
        )
    return OpenAIEmbedder()


__all__ = ["Embedder", "HashEmbedder", "OpenAIEmbedder", "get_embedder"]
