"""
Rate limiter — in-memory sliding-window RPM + SQLite-persisted daily counters.

Every API call (success, retry, 429, timeout, fallback) is counted against
both the RPM and daily budgets.  Counters survive process restarts via SQLite.
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


class RateLimiter:
    """
    Thread-safe within a single asyncio event loop.
    Each provider has:
      - A sliding-window list of call timestamps (last 60s) for RPM.
      - A daily counter persisted in `llm_daily_usage`.
    """

    def __init__(self) -> None:
        # {provider: [unix_timestamp, ...]}
        self._window: dict[str, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_allowed(
        self,
        provider: str,
        rpm_limit: int,
        daily_limit: int,
        db: "aiosqlite.Connection",
    ) -> bool:
        """
        Check (without incrementing) whether a call is permitted.
        Returns False if either the per-minute or daily budget is exhausted.
        """
        # RPM check — prune old timestamps first
        self._prune(provider)
        if len(self._window[provider]) >= rpm_limit:
            return False

        # Daily check — read from SQLite
        count = await self._daily_count(provider, db)
        return count < daily_limit

    async def record(
        self,
        provider: str,
        db: "aiosqlite.Connection",
    ) -> None:
        """
        Increment usage counters.  Must be called after EVERY call attempt
        (success, 429, timeout, fallback — they all count against budget).
        """
        self._window[provider].append(time.monotonic())
        today = date.today().isoformat()
        await db.execute(
            """
            INSERT INTO llm_daily_usage (date, provider, requests)
            VALUES (?, ?, 1)
            ON CONFLICT(date, provider) DO UPDATE SET requests = requests + 1
            """,
            (today, provider),
        )
        await db.commit()

    async def daily_counts(self, db: "aiosqlite.Connection") -> dict[str, int]:
        """Return today's request counts keyed by provider."""
        today = date.today().isoformat()
        async with db.execute(
            "SELECT provider, requests FROM llm_daily_usage WHERE date = ?",
            (today,),
        ) as cur:
            rows = await cur.fetchall()
        return {r[0]: r[1] for r in rows}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _prune(self, provider: str) -> None:
        cutoff = time.monotonic() - 60.0
        self._window[provider] = [t for t in self._window[provider] if t > cutoff]

    async def _daily_count(self, provider: str, db: "aiosqlite.Connection") -> int:
        today = date.today().isoformat()
        async with db.execute(
            "SELECT requests FROM llm_daily_usage WHERE date = ? AND provider = ?",
            (today, provider),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 0


# Module-level singleton shared across the whole pipeline run.
_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
