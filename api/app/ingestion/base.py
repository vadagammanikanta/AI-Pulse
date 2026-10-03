"""Abstract ingester interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.item import Source


@dataclass
class IngestedItem:
    """Raw data extracted from a source — no AI processing yet."""
    external_id: str
    title: str
    url: str
    excerpt: str | None      # hard-capped at 500 chars; NO full text stored
    author: str | None
    published_at: str | None  # ISO-8601 string or None


class BaseIngester(ABC):
    def __init__(self, source: Source) -> None:
        self.source = source

    @abstractmethod
    async def fetch(self) -> list[IngestedItem]:
        """
        Fetch items from the source.
        Must NOT store full article text — excerpt ≤ 500 chars only.
        """
