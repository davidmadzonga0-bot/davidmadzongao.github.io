from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig


@dataclass
class LLMClient:
    config: AppConfig

    @property
    def enabled(self) -> bool:
        return self.config.has_llm

    def complete(self, *, system: str, user: str) -> str | None:
        if not self.enabled:
            return None

        try:
            from openai import OpenAI
        except ImportError:
            return None

        try:
            client = OpenAI(api_key=self.config.openai_api_key)
            response = client.responses.create(
                model=self.config.openai_model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.output_text.strip()
        except Exception:
            return None
