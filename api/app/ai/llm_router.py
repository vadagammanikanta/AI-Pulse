"""
LLM Router — provider fallback chain, per-item validation, per-item retry.

Flow for a list of RawItems:
  1. Cache-check each item (hits go straight to results).
  2. Split misses into batches of LLM_BATCH_SIZE.
  3. For each batch:
       a. Build batch prompt → call providers in priority order.
          - 429/timeout → record_usage() + fall through to next provider.
          - Other error  → record_usage() + fall through.
          - All providers exhausted → batch items stay failed for next run.
       b. Parse the JSON array response.
       c. Validate each element individually with Pydantic.
          Items that fail validation are retried with a single-item prompt
          (up to 3 attempts, cycling through providers again).
       d. Store successful outputs in llm_cache.
  4. Return {raw_item_id: ItemAIOutput} for everything that succeeded.
     Items absent from the result dict must be marked 'failed' by the caller.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.ai.cache import get_cached, store_cached
from app.ai.prompts import build_batch_prompt, build_single_prompt
from app.ai.rate_limiter import get_rate_limiter
from app.ai.providers.base import (
    BaseLLMProvider,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.providers.groq_provider import GroqProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.ollama_provider import OllamaProvider
from app.config import settings
from app.models.item import RawItem
from app.schemas.item import ItemAIOutput

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def _is_ollama_reachable(base_url: str) -> bool:
    import httpx
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{base_url.rstrip('/')}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


def _build_providers() -> list[BaseLLMProvider]:
    """Build active providers in priority order from config."""
    factories = {
        "groq": lambda: GroqProvider(settings),
        "gemini": lambda: GeminiProvider(settings),
        "ollama": lambda: OllamaProvider(settings),
    }
    providers: list[BaseLLMProvider] = []
    for name in settings.llm_provider_order:
        if settings.provider_api_key(name) is None:
            logger.debug("provider_skipped name=%s (no key)", name)
            continue
        if name == "ollama" and not _is_ollama_reachable(settings.ollama_base_url):
            logger.warning(
                "[WARNING] ollama_skipped base_url=%s (not reachable at startup)",
                settings.ollama_base_url,
            )
            continue
        try:
            providers.append(factories[name]())
            logger.info("provider_loaded name=%s model=%s", name, providers[-1].model)
        except (ValueError, KeyError) as exc:
            logger.warning("provider_load_failed name=%s err=%s", name, exc)
    if not providers:
        logger.error("no_providers_configured — all items will fail")
    return providers


# Cache built providers for the lifetime of the process.
_providers: list[BaseLLMProvider] | None = None


def get_providers() -> list[BaseLLMProvider]:
    global _providers
    if _providers is None:
        _providers = _build_providers()
    return _providers


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json_array(text: str) -> list | None:
    """
    Try to extract the first JSON array from the LLM response text.
    Handles markdown fences and extra prose.
    Returns None on malformed / truncated JSON (caller should retry).
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()

    # Try direct parse first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError as exc:
        logger.debug("json_direct_parse_failed err=%s snippet=%r", exc, text[:200])

    # Find first [...] block
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError as exc:
            logger.warning(
                "json_array_parse_failed err=%s snippet=%r — will retry item individually",
                exc, match.group()[:200],
            )

    logger.warning("json_extract_failed — no valid array found in response snippet=%r", text[:200])
    return None


# ---------------------------------------------------------------------------
# Provider call (with fallback chain)
# ---------------------------------------------------------------------------

async def _call_with_fallback(
    prompt: str,
    providers: list[BaseLLMProvider],
    db: "aiosqlite.Connection",
) -> tuple[str, str, str, int, int] | None:
    """
    Try providers in order.  Returns (text, provider_name, model, pt, ct)
    or None if all providers are exhausted.

    429/timeout → record_usage + fall through.
    Other error  → record_usage + fall through.
    """
    limiter = get_rate_limiter()
    failed_chain: list[dict[str, str]] = []

    for provider in providers:
        allowed = await limiter.is_allowed(
            provider.name, provider.rpm_limit, provider.daily_limit, db
        )
        if not allowed:
            logger.info("provider_budget_full name=%s", provider.name)
            failed_chain.append({"provider": provider.name, "status": "budget_exhausted"})
            continue

        try:
            from app.ai.prompts import PROMPT_VERSION
            text, pt, ct = await provider.complete(prompt)
            await limiter.record(provider.name, db)
            if failed_chain:
                logger.info(
                    "[LLM CALL] provider=%s model=%s prompt_version=%s status=fallback failed_providers=%s pt=%d ct=%d",
                    provider.name, provider.model, PROMPT_VERSION, failed_chain, pt, ct,
                )
            else:
                logger.info(
                    "[LLM CALL] provider=%s model=%s prompt_version=%s status=success pt=%d ct=%d",
                    provider.name, provider.model, PROMPT_VERSION, pt, ct,
                )
            return text, provider.name, provider.model, pt, ct

        except (ProviderRateLimitError, ProviderTimeoutError) as exc:
            await limiter.record(provider.name, db)
            status_code = getattr(exc, "status_code", "timeout_or_ratelimit")
            logger.warning(
                "provider_failure name=%s status=%s err=%s — trying fallback provider",
                provider.name, status_code, exc,
            )
            failed_chain.append({"provider": provider.name, "status": str(status_code), "error": str(exc)})
            continue

        except ProviderError as exc:
            await limiter.record(provider.name, db)
            status_code = getattr(exc, "status_code", "error")
            logger.error(
                "provider_failure name=%s status=%s err=%s — trying fallback provider",
                provider.name, status_code, exc,
            )
            failed_chain.append({"provider": provider.name, "status": str(status_code), "error": str(exc)})
            continue

    logger.error("all_providers_exhausted failed_chain=%s", failed_chain)
    return None


# ---------------------------------------------------------------------------
# Single-item retry
# ---------------------------------------------------------------------------

async def _retry_single(
    item: RawItem,
    providers: list[BaseLLMProvider],
    db: "aiosqlite.Connection",
    max_attempts: int = 3,
) -> ItemAIOutput | None:
    """Retry a single item up to max_attempts times with full provider fallback each time."""
    from app.ai.prompts import PROMPT_VERSION
    prompt = build_single_prompt(item)
    for attempt in range(1, max_attempts + 1):
        raw = await _call_with_fallback(prompt, providers, db)
        if raw is None:
            logger.warning("single_retry_no_provider item_id=%d attempt=%d", item.id, attempt)
            return None

        text, p_name, p_model, pt, ct = raw
        arr = _extract_json_array(text)
        if not arr:
            logger.warning("single_retry_parse_fail item_id=%d attempt=%d", item.id, attempt)
            continue

        try:
            output = ItemAIOutput.model_validate(arr[0])
            await store_cached(item.title, item.url, output, p_name, p_model, PROMPT_VERSION, pt, ct, db)
            return output
        except ValidationError as exc:
            logger.warning(
                "single_retry_validation_fail item_id=%d attempt=%d err=%s",
                item.id, attempt, exc,
            )

    logger.error("single_retry_exhausted item_id=%d title=%r", item.id, item.title)
    return None


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

async def _process_batch(
    batch: list[RawItem],
    providers: list[BaseLLMProvider],
    db: "aiosqlite.Connection",
) -> dict[int, ItemAIOutput]:
    from app.ai.prompts import PROMPT_VERSION
    results: dict[int, ItemAIOutput] = {}
    prompt = build_batch_prompt(batch)

    raw = await _call_with_fallback(prompt, providers, db)
    if raw is None:
        logger.error("batch_all_providers_exhausted count=%d", len(batch))
        return results

    text, p_name, p_model, pt, ct = raw
    arr = _extract_json_array(text)

    if arr is None:
        logger.warning("batch_parse_failed — retrying all %d individually", len(batch))
        for item in batch:
            out = await _retry_single(item, providers, db)
            if out:
                results[item.id] = out
        return results

    # Apportion token counts equally across batch items (approximation)
    per_item_pt = max(pt // len(batch), 1)
    per_item_ct = max(ct // len(batch), 1)

    failed_items: list[RawItem] = []
    for i, item in enumerate(batch):
        if i >= len(arr):
            logger.warning("batch_missing_element item_id=%d index=%d", item.id, i)
            failed_items.append(item)
            continue
        try:
            output = ItemAIOutput.model_validate(arr[i])
            results[item.id] = output
            await store_cached(
                item.title, item.url, output, p_name, p_model, PROMPT_VERSION, per_item_pt, per_item_ct, db
            )
        except ValidationError as exc:
            logger.warning(
                "batch_item_validation_fail item_id=%d err=%s — queuing retry", item.id, exc
            )
            failed_items.append(item)

    # Retry only the failed items — not the entire batch
    for item in failed_items:
        out = await _retry_single(item, providers, db)
        if out:
            results[item.id] = out

    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def summarize_items(
    items: list[RawItem],
    db: "aiosqlite.Connection",
) -> dict[int, ItemAIOutput]:
    """
    Summarize a list of RawItems.
    Returns {raw_item_id: ItemAIOutput} for every item that succeeded.
    Items not in the result must be marked 'failed' by the caller.
    """
    if not items:
        return {}

    from app.ai.prompts import PROMPT_VERSION
    providers = get_providers()
    primary_model = providers[0].model if providers else "unknown"

    results: dict[int, ItemAIOutput] = {}
    cache_misses: list[RawItem] = []

    # 1. Cache check using title, url, PROMPT_VERSION, and primary provider model
    for item in items:
        cached = await get_cached(item.title, item.url, PROMPT_VERSION, primary_model, db)
        if cached:
            results[item.id] = cached
            logger.info("cache_hit item_id=%d ver=%s model=%s", item.id, PROMPT_VERSION, primary_model)
        else:
            cache_misses.append(item)

    if not cache_misses:
        return results

    # 2. Batch processing
    batch_size = settings.llm_batch_size
    batches = [
        cache_misses[i : i + batch_size]
        for i in range(0, len(cache_misses), batch_size)
    ]
    logger.info(
        "llm_batching total=%d batches=%d batch_size=%d",
        len(cache_misses), len(batches), batch_size,
    )

    for batch in batches:
        batch_results = await _process_batch(batch, providers, db)
        results.update(batch_results)

    return results
