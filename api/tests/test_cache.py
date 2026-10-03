"""Tests for LLM cache key hashing with PROMPT_VERSION and model name."""
import pytest
import aiosqlite
from app.ai.cache import get_cached, store_cached
from app.database import init_db
from app.schemas.item import ItemAIOutput, LearningModule


@pytest.mark.asyncio
async def test_cache_miss_on_prompt_version_or_model_change():
    sample_output = ItemAIOutput(
        what_is_new="Authors report new findings",
        why_it_matters="Improves training speed",
        who_should_care=["developers"],
        how_to_use="Run the provided evaluation script",
        pro_tip="Monitor GPU usage during runs",
        category="model",
        importance_score=85,
        importance_reason="Significant speedup",
        learning_module=LearningModule(
            tutorial_5min="1. Load model. 2. Run inference.",
            practice_task="Evaluate on a custom benchmark.",
            challenge="Scale to multi-node cluster.",
            skill_gained="Model Optimization",
            next_topic="Distributed Training",
        ),
    )

    async with aiosqlite.connect(":memory:") as db:
        await init_db(db)

        # Store cached entry with v2.0 and model A
        await store_cached(
            title="Sample Model Launch",
            url="http://example.com/model-a",
            output=sample_output,
            provider="groq",
            model="model-a",
            prompt_version="v2.0",
            prompt_tokens=100,
            completion_tokens=50,
            db=db,
        )

        # 1. Exact match should hit
        hit = await get_cached("Sample Model Launch", "http://example.com/model-a", "v2.0", "model-a", db)
        assert hit is not None
        assert hit.what_is_new == "Authors report new findings"

        # 2. Different prompt version should miss
        miss_ver = await get_cached("Sample Model Launch", "http://example.com/model-a", "v2.1", "model-a", db)
        assert miss_ver is None

        # 3. Different model name should miss
        miss_model = await get_cached("Sample Model Launch", "http://example.com/model-a", "v2.0", "model-b", db)
        assert miss_model is None
