"""Internal data models (dataclasses). Not exposed via the API directly."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Source:
    id: int
    name: str
    type: str
    url: str
    feed_url: str | None
    active: bool
    fetch_interval_minutes: int
    config_json: str
    source_weight: int
    last_fetched_at: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Source":
        return cls(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            url=row["url"],
            feed_url=row["feed_url"],
            active=bool(row["active"]),
            fetch_interval_minutes=row["fetch_interval_minutes"],
            config_json=row["config_json"],
            source_weight=row["source_weight"],
            last_fetched_at=row["last_fetched_at"],
            created_at=row["created_at"],
        )

    @property
    def config(self) -> dict:
        try:
            return json.loads(self.config_json)
        except (json.JSONDecodeError, TypeError):
            return {}


@dataclass
class RawItem:
    id: int
    source_id: int
    external_id: str
    title: str
    url: str
    excerpt: str | None
    author: str | None
    published_at: str | None
    ingested_at: str
    status: str
    pre_score: int | None
    error_message: str | None
    failed_prompt_version: str | None = None
    attempts: int = 0
    # Joined fields (not always present)
    source_name: str | None = None
    source_weight: int | None = None

    @classmethod
    def from_row(cls, row) -> "RawItem":
        keys = row.keys()
        return cls(
            id=row["id"],
            source_id=row["source_id"],
            external_id=row["external_id"],
            title=row["title"],
            url=row["url"],
            excerpt=row["excerpt"],
            author=row["author"],
            published_at=row["published_at"],
            ingested_at=row["ingested_at"],
            status=row["status"],
            pre_score=row["pre_score"],
            error_message=row["error_message"],
            failed_prompt_version=row["failed_prompt_version"] if "failed_prompt_version" in keys else None,
            attempts=row["attempts"] if "attempts" in keys else 0,
            source_name=row["name"] if "name" in keys else None,
            source_weight=row["source_weight"] if "source_weight" in keys else None,
        )


@dataclass
class Item:
    id: int
    raw_item_id: int | None
    source_id: int
    title: str
    url: str
    author: str | None
    published_at: str | None
    category: str
    importance_score: int
    importance_reason: str | None
    what_is_new: str | None
    why_it_matters: str | None
    who_should_care_json: str
    how_to_use: str | None
    pro_tip: str | None
    learning_module_json: str
    embedding: bytes | None
    embedding_model: str | None
    saved: bool
    processed_at: str
    # Joined
    source_name: str | None = None

    @classmethod
    def from_row(cls, row) -> "Item":
        return cls(
            id=row["id"],
            raw_item_id=row["raw_item_id"],
            source_id=row["source_id"],
            title=row["title"],
            url=row["url"],
            author=row["author"],
            published_at=row["published_at"],
            category=row["category"],
            importance_score=row["importance_score"],
            importance_reason=row["importance_reason"],
            what_is_new=row["what_is_new"],
            why_it_matters=row["why_it_matters"],
            who_should_care_json=row["who_should_care_json"],
            how_to_use=row["how_to_use"],
            pro_tip=row["pro_tip"],
            learning_module_json=row["learning_module_json"],
            embedding=row["embedding"],
            embedding_model=row["embedding_model"],
            saved=bool(row["saved"]),
            processed_at=row["processed_at"],
            source_name=row["source_name"] if "source_name" in row.keys() else None,
        )

    @property
    def who_should_care(self) -> list[str]:
        try:
            return json.loads(self.who_should_care_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def learning_module(self) -> dict:
        try:
            return json.loads(self.learning_module_json)
        except (json.JSONDecodeError, TypeError):
            return {}
