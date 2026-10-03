"""Prompt templates for LLM summarization."""
from __future__ import annotations

from app.models.item import RawItem

PROMPT_VERSION = "v2.2"

# ---------------------------------------------------------------------------
# Batch prompt (N items → JSON array of N objects)
# ---------------------------------------------------------------------------

_BATCH_SYSTEM = """\
You are an expert AI analyst. Your job is to analyse AI/ML news items and produce \
structured JSON. Return ONLY a valid JSON array — no markdown fences, no explanation, \
no preamble. Each element corresponds to the input item at the same index.

ABSOLUTE RULES — violating any of these causes the output to be discarded:
1. ATTRIBUTION: Always attribute novelty and capability claims to the authors or creators \
(use phrases like "The authors claim...", "According to the creators...", "The team reports..."). \
Never state unverified claims as fact.
2. SOURCE-ONLY: Never invent package names, CLI commands, pip install commands, URLs, API endpoints, \
filenames, repos, section numbers, README references, appendix references, demo names, \
or "Getting Started" sections. Only reference tools, libraries, commands, or code explicitly \
present in the source title or excerpt.
3. THIN EXCERPT: If the excerpt is too thin for a learning guide, set learning_module to null. \
Do not pad with invented content.

JSON schema for each element — EXACTLY this shape, no extra fields:
{
  "what_is_new": "<1-3 sentences: what the authors/creators report, attributed>",
  "why_it_matters": "<1-3 sentences: practical significance, attributed>",
  "who_should_care": ["developers","students","businesses"],
  "how_to_use": "<2-5 sentences: concrete first steps, source-verifiable only>",
  "pro_tip": "<1 sentence: a non-obvious insight from the excerpt>",
  "category": "<exactly one of: news|model|tool|api|paper|company>",
  "importance_score": <integer 0-100>,
  "importance_reason": "<1 sentence: why this score>",
  "learning_module": {
    "key_idea": "<Core contribution or announcement in 1-2 sentences, attributed.>",
    "read_for": "<What to focus on or evaluate while reviewing this item.>",
    "prerequisite_concepts": ["<concept 1>", "<concept 2>"],
    "skill_gained": "<Skill or insight gained, 3-6 words.>",
    "next_topic": "<Logical follow-up topic or area to explore.>"
  }
}

LEARNING MODULE RULES (applies to ALL categories):
Forbidden in learning_module: numbered tutorial steps, Section N, appendix, README, \
demo, provided, repo, any filename (*.py, *.ipynb, *.json, etc.), getting started, \
unverified CLI / pip / git commands.

Scoring guide: 90-100 = major release/breakthrough, 70-89 = significant update,
50-69 = useful news, 30-49 = minor, <30 = low-signal.
"""

_ITEM_TEMPLATE = """\
--- ITEM {n} ---
Title: {title}
Source: {source}
Published: {published_at}
Excerpt: {excerpt}
URL: {url}
"""


def build_batch_prompt(items: list[RawItem]) -> str:
    item_blocks = "".join(
        _ITEM_TEMPLATE.format(
            n=i + 1,
            title=item.title,
            source=item.source_name or "unknown",
            published_at=item.published_at or "unknown",
            excerpt=item.excerpt or "(no excerpt)",
            url=item.url,
        )
        for i, item in enumerate(items)
    )
    return (
        f"{_BATCH_SYSTEM}\n\nAnalyse the following {len(items)} item(s) "
        f"and return a JSON array of exactly {len(items)} object(s):\n\n{item_blocks}"
    )


def build_single_prompt(item: RawItem) -> str:
    """Single-item prompt — response should be a JSON array of 1 element."""
    return build_batch_prompt([item])
