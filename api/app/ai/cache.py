"""LLM result cache — keyed by sha256 of "title|url|prompt_version|model"."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

from app.schemas.item import ItemAIOutput

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)


def _make_hash(title: str, url: str, prompt_version: str, model: str) -> str:
    key = f"{title.strip().lower()}|{url.strip().lower()}|{prompt_version.strip()}|{model.strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()


async def get_cached(
    title: str,
    url: str,
    prompt_version: str,
    model: str,
    db: "aiosqlite.Connection",
) -> ItemAIOutput | None:
    """Return a cached ItemAIOutput for the specific prompt_version and model, or None on miss."""
    h = _make_hash(title, url, prompt_version, model)
    async with db.execute(
        "SELECT output_json FROM llm_cache WHERE content_hash = ?",
        (h,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        return None

    try:
        data = json.loads(row[0])
        result = ItemAIOutput.model_validate(data)
        logger.debug("llm_cache_hit hash=%s ver=%s model=%s", h[:12], prompt_version, model)
        return result
    except Exception as exc:
        logger.warning("llm_cache_corrupt hash=%s err=%s — treating as miss", h[:12], exc)
        return None


async def store_cached(
    title: str,
    url: str,
    output: ItemAIOutput,
    provider: str,
    model: str,
    prompt_version: str,
    prompt_tokens: int,
    completion_tokens: int,
    db: "aiosqlite.Connection",
) -> None:
    """Persist a successful ItemAIOutput to the LLM cache keyed by title, url, prompt_version, and model."""
    h = _make_hash(title, url, prompt_version, model)
    output_json = output.model_dump_json()
    await db.execute(
        """
        INSERT OR IGNORE INTO llm_cache
            (content_hash, provider, model, output_json, prompt_tokens, completion_tokens)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (h, provider, model, output_json, prompt_tokens, completion_tokens),
    )
    await db.commit()
    logger.debug("llm_cache_stored hash=%s provider=%s ver=%s model=%s", h[:12], provider, prompt_version, model)
