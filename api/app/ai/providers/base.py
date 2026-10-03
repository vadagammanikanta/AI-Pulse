"""Abstract base for LLM providers."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Non-retryable provider error (e.g. bad API key, 5xx)."""


class ProviderRateLimitError(ProviderError):
    """429 or quota exceeded — fall through to next provider."""


class ProviderTimeoutError(ProviderError):
    """Request timeout — fall through to next provider."""


class BaseLLMProvider(ABC):
    """
    Contract for every LLM provider.

    complete() returns (text, prompt_tokens, completion_tokens).
    Raises ProviderRateLimitError or ProviderTimeoutError for transient
    issues that should cause fall-through; raises ProviderError for
    non-retryable failures.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def model(self) -> str: ...

    @property
    @abstractmethod
    def rpm_limit(self) -> int: ...

    @property
    @abstractmethod
    def daily_limit(self) -> int: ...

    @abstractmethod
    async def complete(self, prompt: str) -> tuple[str, int, int]:
        """Returns (text, prompt_tokens, completion_tokens)."""
