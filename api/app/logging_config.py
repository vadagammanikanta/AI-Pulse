"""
Logging configuration and secret masking filter.

The SecretMaskingFilter replaces any occurrence of a registered secret
with its first 4 characters followed by '****'. This prevents API keys,
tokens, and passwords from appearing in log output.

Usage:
    from app.logging_config import configure_logging
    configure_logging()   # call once at startup, before any logging

The filter is also registered on the root logger so it catches all handlers.
"""
from __future__ import annotations

import logging
import re


# ---------------------------------------------------------------------------
# Secret masking
# ---------------------------------------------------------------------------

class SecretMaskingFilter(logging.Filter):
    """
    A logging.Filter that masks registered secrets in log records.

    Secrets shorter than 8 characters are not masked (they are not meaningful
    API keys and masking them would produce false positives in normal text).
    """

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._patterns: list[tuple[re.Pattern, str]] = []
        for secret in (secrets or []):
            self._register(secret)

    def _register(self, secret: str) -> None:
        if not secret or len(secret) < 8:
            return
        prefix = secret[:4]
        replacement = f"{prefix}****"
        # Escape the secret so it's safe as a regex literal
        pattern = re.compile(re.escape(secret))
        self._patterns.append((pattern, replacement))

    def add_secret(self, secret: str) -> None:
        """Dynamically add a new secret to mask. Thread-safe for reads."""
        self._register(secret)

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask secrets in the formatted message and all record arguments."""
        if self._patterns:
            # Mask in the format string
            if isinstance(record.msg, str):
                for pattern, replacement in self._patterns:
                    record.msg = pattern.sub(replacement, record.msg)

            # Mask in positional args
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: _mask_value(v, self._patterns) for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        _mask_value(a, self._patterns) for a in record.args
                    )

        return True  # always emit — we only mutate, never suppress


def _mask_value(value: object, patterns: list[tuple[re.Pattern, str]]) -> object:
    """Apply all masking patterns to a single log argument if it's a string."""
    if isinstance(value, str):
        for pattern, replacement in patterns:
            value = pattern.sub(replacement, value)
    return value


# ---------------------------------------------------------------------------
# Module-level singleton filter
# ---------------------------------------------------------------------------

_global_filter = SecretMaskingFilter()


def register_secret(secret: str | None) -> None:
    """Register a secret to be masked in all future log output."""
    if secret:
        _global_filter.add_secret(secret)


def configure_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with a stream handler + secret masking filter.
    Call once at application startup (e.g. in main.py lifespan).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid adding duplicate handlers on reload
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        root.addHandler(handler)

    # Install masking filter on every existing handler (and root)
    root.addFilter(_global_filter)
    for handler in root.handlers:
        handler.addFilter(_global_filter)
