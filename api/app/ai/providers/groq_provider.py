"""Groq provider (free tier — llama-3.x via Groq cloud)."""
from __future__ import annotations

import asyncio
import logging

from groq import AsyncGroq
from groq import APIStatusError, APITimeoutError

from app.ai.providers.base import (
    BaseLLMProvider,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.config import Settings

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    def __init__(self, cfg: Settings) -> None:
        if not cfg.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self._client = AsyncGroq(api_key=cfg.groq_api_key)
        self._model = cfg.groq_model
        self._rpm = cfg.groq_rpm
        self._daily = cfg.groq_daily_limit

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return self._model

    @property
    def rpm_limit(self) -> int:
        return self._rpm

    @property
    def daily_limit(self) -> int:
        return self._daily

    async def complete(self, prompt: str) -> tuple[str, int, int]:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4096,
            )
            content = resp.choices[0].message.content or ""
            pt = resp.usage.prompt_tokens if resp.usage else 0
            ct = resp.usage.completion_tokens if resp.usage else 0
            logger.debug("groq_ok model=%s pt=%d ct=%d", self._model, pt, ct)
            return content, pt, ct

        except APITimeoutError as exc:
            raise ProviderTimeoutError(f"Groq timeout: {exc}") from exc

        except APIStatusError as exc:
            code = exc.status_code
            if code == 429:
                raise ProviderRateLimitError(f"Groq 429: {exc}") from exc
            if code >= 500:
                raise ProviderError(f"Groq {code}: {exc}") from exc
            # 4xx except 429 → non-retryable (bad key, model not found, …)
            raise ProviderError(f"Groq {code}: {exc}") from exc

        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError(f"Groq asyncio timeout") from exc

        except Exception as exc:
            raise ProviderError(f"Groq unexpected error: {exc}") from exc
