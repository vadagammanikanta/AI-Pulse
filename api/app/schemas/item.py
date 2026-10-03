"""Pydantic v2 schemas for API request/response."""
from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# LLM output schema  (validated per-item from LLM JSON)
# ---------------------------------------------------------------------------

class PaperLearningModule(BaseModel):
    """Learning module for academic papers (category='paper').
    No numbered steps, section references, demos, scripts, repos, or filenames.
    All content must be derivable from the title and excerpt alone.
    """
    module_type: Literal["paper"] = "paper"
    key_idea: str | None = Field(default=None, description="Core contribution in 1-2 sentences, attributed to authors.")
    read_for: str | None = Field(default=None, description="What to look for while reading (method, eval, claims).")
    prerequisite_concepts: list[str] | None = Field(default=None, description="2-4 concepts needed to understand the paper.")
    skill_gained: str | None = Field(default=None, description="Skill gained from understanding this paper, 3-6 words.")
    next_topic: str | None = Field(default=None, description="Logical follow-up topic or paper to read next.")


class TutorialLearningModule(BaseModel):
    """Learning module for non-paper items (tools, news, models, APIs, companies).
    Restrict tutorial_5min to concepts and actions possible from the excerpt only.
    """
    module_type: Literal["tutorial"] = "tutorial"
    tutorial_5min: str | None = Field(default=None, description="2-5 step tutorial restricted to excerpt content.")
    practice_task: str | None = Field(default=None, description="Specific hands-on task or null.")
    challenge: str | None = Field(default=None, description="Harder extension or null.")
    skill_gained: str | None = Field(default=None, description="Skill name, 3-6 words.")
    next_topic: str | None = Field(default=None, description="Logical follow-up topic.")


# Legacy alias kept for backward compat (DB rows stored pre-schema change)
LearningModule = TutorialLearningModule

AnyLearningModule = Annotated[
    PaperLearningModule | TutorialLearningModule,
    Field(discriminator="module_type"),
]


class ItemAIOutput(BaseModel):
    what_is_new: str = Field(..., min_length=1)
    why_it_matters: str = Field(..., min_length=1)
    who_should_care: list[str] = Field(..., min_length=1)
    how_to_use: str = Field(..., min_length=1)
    pro_tip: str = Field(..., min_length=1)
    category: Literal["news", "model", "tool", "api", "paper", "company"]
    importance_score: int = Field(..., ge=0, le=100)
    importance_reason: str = Field(..., min_length=1)
    learning_module: PaperLearningModule | TutorialLearningModule | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_and_normalize(cls, values):
        # Coerce who_should_care from comma-string to list
        wsc = values.get("who_should_care")
        if isinstance(wsc, str):
            values["who_should_care"] = [s.strip() for s in wsc.split(",") if s.strip()]

        # Inject module_type into learning_module so Pydantic can discriminate.
        # Currently all items use paper reading-note schema until docs text is fetched.
        lm = values.get("learning_module")
        if isinstance(lm, dict) and "module_type" not in lm:
            lm["module_type"] = "paper"
            values["learning_module"] = lm
        return values


# ---------------------------------------------------------------------------
# Feed / list schema
# ---------------------------------------------------------------------------

class FeedItem(BaseModel):
    id: int
    title: str
    url: str
    author: str | None
    published_at: str | None
    category: str
    importance_score: int
    importance_reason: str | None
    what_is_new: str | None
    why_it_matters: str | None
    who_should_care: list[str]
    saved: bool
    processed_at: str
    source_name: str | None
    feed_score: float = 0.0
    matched_keywords: list[str] = Field(default_factory=list)
    match_type: Literal["keyword", "semantic", "hybrid"] | None = None

    @classmethod
    def from_row(cls, row) -> "FeedItem":
        return cls(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            author=row["author"],
            published_at=row["published_at"],
            category=row["category"],
            importance_score=row["importance_score"],
            importance_reason=row["importance_reason"],
            what_is_new=row["what_is_new"],
            why_it_matters=row["why_it_matters"],
            who_should_care=_parse_json_list(row["who_should_care_json"]),
            saved=bool(row["saved"]),
            processed_at=row["processed_at"],
            source_name=row["source_name"] if "source_name" in row.keys() else None,
            feed_score=float(row["feed_score"]) if "feed_score" in row.keys() and row["feed_score"] is not None else 0.0,
            matched_keywords=_parse_json_list(row["matched_keywords_json"]) if "matched_keywords_json" in row.keys() else [],
        )


# ---------------------------------------------------------------------------
# Item detail schema
# ---------------------------------------------------------------------------

class ItemDetail(FeedItem):
    how_to_use: str | None
    pro_tip: str | None
    learning_module: dict | None

    @classmethod
    def from_row(cls, row) -> "ItemDetail":
        base = FeedItem.from_row(row)
        return cls(
            **base.model_dump(),
            how_to_use=row["how_to_use"],
            pro_tip=row["pro_tip"],
            learning_module=_parse_json_dict(row["learning_module_json"]),
        )


# ---------------------------------------------------------------------------
# Save / unsave
# ---------------------------------------------------------------------------

class SaveResponse(BaseModel):
    item_id: int
    saved: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
