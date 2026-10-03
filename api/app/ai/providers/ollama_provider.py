"""Ollama provider — local, zero cost, no API key."""
from __future__ import annotations

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

_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)


class OllamaProvider(BaseLLMProvider):
    def __init__(self, cfg: Settings) -> None:
        self._base_url = cfg.ollama_base_url.rstrip("/")
        self._model_name = cfg.ollama_model
        self._rpm = cfg.ollama_rpm
        self._daily = cfg.ollama_daily_limit

    @property
    def name(self) -> str:
        return "ollama"

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
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)

            if resp.status_code == 429:
                raise ProviderRateLimitError("Ollama 429")

            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "")
            pt = data.get("prompt_eval_count", 0) or 0
            ct = data.get("eval_count", 0) or 0
            logger.debug("ollama_ok model=%s pt=%d ct=%d", self._model_name, pt, ct)
            return text, pt, ct

        except ProviderRateLimitError:
            raise

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Ollama timeout: {exc}") from exc

        except httpx.ConnectError as exc:
            raise ProviderError(f"Ollama not reachable at {self._base_url}: {exc}") from exc

        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Ollama HTTP {exc.response.status_code}: {exc}") from exc

        except Exception as exc:
            raise ProviderError(f"Ollama unexpected: {exc}") from exc
