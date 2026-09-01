from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import os

from sec_filings.config import OPENAI_CHAT_MODEL


class LLM(ABC):
    @abstractmethod
    def complete(self, prompt: str, system_prompt: str) -> dict[str, Any]:
        raise NotImplementedError


class MockLLM(LLM):
    def complete(self, prompt: str, system_prompt: str) -> dict[str, Any]:
        excerpt = prompt[-400:]
        return {
            "success": True,
            "content": f"[mock answer] {excerpt}",
            "usage": None,
            "model": "mock",
        }


class OpenAILLM(LLM):
    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self.model = model or OPENAI_CHAT_MODEL
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def complete(self, prompt: str, system_prompt: str) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        content = ""
        if response.choices:
            content = response.choices[0].message.content or ""
        return {
            "success": True,
            "content": content,
            "usage": usage,
            "model": self.model,
        }


def get_llm() -> LLM:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if provider == "mock":
        return MockLLM()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Provide a key or set LLM_PROVIDER=mock."
        )
    return OpenAILLM()
