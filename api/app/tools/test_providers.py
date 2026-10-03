"""
Live provider test — one call per configured provider.

Usage:
  python -m app.tools.test_providers

Prints, for each configured provider:
  [OK]  provider=groq  model=... response_preview="..."
  [ERR] provider=gemini model=... error="..."
"""
from __future__ import annotations

import asyncio
import logging
import sys

import aiosqlite

from app.ai.llm_router import _build_providers
from app.ai.providers.base import ProviderError
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_TEST_PROMPT = (
    '[{"what_is_new":"Test item","why_it_matters":"N/A",'
    '"who_should_care":["developers"],"how_to_use":"N/A",'
    '"pro_tip":"N/A","category":"news","importance_score":50,'
    '"importance_reason":"test","learning_module":null}]\n\n'
    "Return a JSON array with exactly 1 object using this schema. "
    "Title: Provider connectivity test. Excerpt: This is a test."
)


async def test_all_providers() -> None:
    from app.logging_config import configure_logging, register_secret
    configure_logging("INFO")
    register_secret(settings.api_secret_key)
    register_secret(settings.groq_api_key)
    register_secret(settings.gemini_api_key)
    register_secret(settings.telegram_bot_token)

    db_path = settings.db_path
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await init_db(db)

        providers = _build_providers()
        if not providers:
            print("[WARN] No providers configured. Set at least one API key in .env")
            return

        any_error = False
        from app.logging_config import _global_filter, _mask_value
        for provider in providers:
            print(f"\nTesting provider={provider.name!r} model={provider.model!r} ...")
            try:
                text, pt, ct = await provider.complete(_TEST_PROMPT)
                preview = text[:120].replace("\n", " ")
                print(f"  [OK]  pt={pt} ct={ct} response_preview={preview!r}")
            except ProviderError as exc:
                err_msg = str(_mask_value(str(exc), _global_filter._patterns))
                print(f"  [ERR] status={getattr(exc, 'status_code', '?')} error={err_msg}")
                any_error = True
            except Exception as exc:
                err_msg = str(_mask_value(str(exc), _global_filter._patterns))
                print(f"  [ERR] unexpected error={err_msg}")
                any_error = True

        print()
        if any_error:
            print("Some providers failed — check .env and API keys above.")
            sys.exit(1)
        else:
            print("All providers responded successfully.")


def main() -> None:
    asyncio.run(test_all_providers())


if __name__ == "__main__":
    main()
