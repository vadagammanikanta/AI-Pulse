"""
Force-regeneration CLI tool — re-summarizes existing items with the current prompt.

Usage:
  python -m app.tools.regenerate --limit 10
  python -m app.tools.regenerate --limit 10 --include-papers
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

import aiosqlite

from app.ai.embedder import embed_text
from app.ai.llm_router import get_providers, _call_with_fallback, _extract_json_array
from app.ai.prompts import build_single_prompt, PROMPT_VERSION
from app.ai.validator import sanitize_item_output
from app.config import settings
from app.database import init_db
from app.models.item import RawItem
from app.schemas.item import ItemAIOutput

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def run_regeneration(limit: int, include_papers: bool) -> None:
    db_path = settings.db_path
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await init_db(db)

        # Build query for target items
        paper_filter = (
            "AND (ri.url LIKE '%arxiv%' or ri.source_id IN "
            "(SELECT id FROM sources WHERE type='arxiv' or name LIKE '%arxiv%'))"
            if include_papers else ""
        )
        query = f"""
            SELECT ri.*, s.name AS source_name, s.source_weight
            FROM raw_items ri
            JOIN sources s ON ri.source_id = s.id
            WHERE ri.status IN ('processed', 'pending', 'skipped') {paper_filter}
            ORDER BY ri.id DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cur:
            rows = await cur.fetchall()

        if not rows:
            logger.warning("no_items_found_for_regeneration limit=%d papers=%s", limit, include_papers)
            return

        raw_items = [RawItem.from_row(r) for r in rows]
        providers = get_providers()
        logger.info("force_regenerating count=%d ver=%s providers=%s", len(raw_items), PROMPT_VERSION, [p.name for p in providers])

        counts = {"passed": 0, "nulled": 0, "skipped": 0, "failed": 0}

        for item in raw_items:
            prompt = build_single_prompt(item)
            raw_resp = await _call_with_fallback(prompt, providers, db)
            if not raw_resp:
                logger.error("regen_failed item_id=%d title=%r", item.id, item.title)
                counts["failed"] += 1
                continue

            text, p_name, p_model, pt, ct = raw_resp
            arr = _extract_json_array(text)
            if not arr:
                logger.warning("regen_json_parse_failed item_id=%d — skipping (malformed JSON)", item.id)
                counts["failed"] += 1
                continue

            try:
                output = ItemAIOutput.model_validate(arr[0])
            except Exception as exc:
                logger.warning("regen_validation_failed item_id=%d err=%s", item.id, exc)
                counts["failed"] += 1
                continue

            # Run automated hallucination validator (now returns a tuple)
            output, vr = sanitize_item_output(output, item.title, item.excerpt)
            counts[vr] = counts.get(vr, 0) + 1

            # Re-embed
            embed_text_input = f"{item.title}. {output.what_is_new}"
            embedding = await embed_text(embed_text_input)

            # Upsert into items table including validator_result
            lm_json = output.learning_module.model_dump_json() if output.learning_module else "{}"
            wsc_json = json.dumps(output.who_should_care)

            # Apply arXiv category and importance capping rule
            from app.pipeline.ranker import apply_arxiv_rule
            category, importance_score = apply_arxiv_rule(
                item.url, item.source_name, item.title, item.excerpt, output.category, output.importance_score
            )

            await db.execute(
                """
                INSERT INTO items (
                    raw_item_id, source_id, title, url, author, published_at,
                    category, importance_score, importance_reason,
                    what_is_new, why_it_matters, who_should_care_json,
                    how_to_use, pro_tip, learning_module_json,
                    embedding, embedding_model, validator_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(raw_item_id) DO UPDATE SET
                    category = excluded.category,
                    importance_score = excluded.importance_score,
                    importance_reason = excluded.importance_reason,
                    what_is_new = excluded.what_is_new,
                    why_it_matters = excluded.why_it_matters,
                    who_should_care_json = excluded.who_should_care_json,
                    how_to_use = excluded.how_to_use,
                    pro_tip = excluded.pro_tip,
                    learning_module_json = excluded.learning_module_json,
                    embedding = excluded.embedding,
                    embedding_model = excluded.embedding_model,
                    validator_result = excluded.validator_result,
                    processed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                """,
                (
                    item.id,
                    item.source_id,
                    item.title,
                    item.url,
                    item.author,
                    item.published_at,
                    category,
                    importance_score,
                    output.importance_reason,
                    output.what_is_new,
                    output.why_it_matters,
                    wsc_json,
                    output.how_to_use,
                    output.pro_tip,
                    lm_json,
                    embedding,
                    settings.embedding_model,
                    vr,
                ),
            )
            await db.commit()
            logger.info(
                "item_regenerated raw_item_id=%d category=%s validator=%s title=%r",
                item.id, output.category, vr, item.title,
            )

        print(
            f"\n=== Regeneration complete (PROMPT_VERSION={PROMPT_VERSION}) ===\n"
            f"  passed : {counts['passed']}\n"
            f"  nulled : {counts['nulled']}\n"
            f"  skipped: {counts['skipped']}\n"
            f"  failed : {counts['failed']}\n"
            f"  total  : {sum(counts.values())}\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Force-regenerate items with current LLM prompt")
    parser.add_argument("--limit", type=int, default=10, help="Number of items to regenerate")
    parser.add_argument("--include-papers", action="store_true", help="Filter for papers/arXiv items")
    args = parser.parse_args()

    asyncio.run(run_regeneration(args.limit, args.include_papers))
    sys.exit(0)


if __name__ == "__main__":
    main()
