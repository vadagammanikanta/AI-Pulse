"""Gemini provider (Google AI — free tier via REST API)."""
from __future__ import annotations

import asyncio
import logging
import httpx

from app.ai.providers.base import (
    BaseLLMProvider,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.config import Settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)


class GeminiProvider(BaseLLMProvider):
    def __init__(self, cfg: Settings) -> None:
        if not cfg.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self._api_key = cfg.gemini_api_key
        self._model_name = cfg.gemini_model
        self._rpm = cfg.gemini_rpm
        self._daily = cfg.gemini_daily_limit

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def rpm_limit(self) -> int:
        return self._rpm

    @property
    def daily_limit(self) -> int:
        return self._daily

    async def complete(self, prompt: str) -> tuple[str, int, int]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent?key={self._api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code == 429:
                raise ProviderRateLimitError(f"Gemini 429 quota: {resp.text}")

            if resp.status_code >= 500:
                raise ProviderError(f"Gemini server error {resp.status_code}: {resp.text}")

            resp.raise_for_status()
            data = resp.json()

            text = ""
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "")

            meta = data.get("usageMetadata", {})
            pt = meta.get("promptTokenCount", 0) or 0
            ct = meta.get("candidatesTokenCount", 0) or 0

            logger.debug("gemini_ok model=%s pt=%d ct=%d", self._model_name, pt, ct)
            return text, pt, ct

        except ProviderRateLimitError:
            raise

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Gemini timeout: {exc}") from exc

        except httpx.HTTPStatusError as exc:
            msg = str(exc)
            if exc.response.status_code == 429 or "quota" in msg.lower():
                raise ProviderRateLimitError(f"Gemini rate limit: {exc}") from exc
            raise ProviderError(f"Gemini HTTP {exc.response.status_code}: {exc}") from exc

        except Exception as exc:
            raise ProviderError(f"Gemini unexpected: {exc}") from exc
