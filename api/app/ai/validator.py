"""
Hallucination guardrail for learning modules.

Detects two classes of problems:
  1. Invented software artifacts: pip install, git clone, URLs, etc.
  2. Invented structural artifacts: section numbers, appendix references,
     README references, filenames, demos, repos, "Getting Started" sections.

Any flagged term that is NOT present verbatim in the source title+excerpt
causes learning_module to be set to None and validator_result to "nulled".

Returns (sanitized_output, validator_result) where validator_result is one of:
  "passed"  — module kept; no bad patterns found
  "nulled"  — module set to None; invented artifact detected
  "skipped" — no learning_module present; nothing to check
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.item import ItemAIOutput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern groups
# ---------------------------------------------------------------------------

# Group 1: Software installation / cloning / URLs
# Capture group 1 is the entity name when present.
_INSTALL_PATTERNS: list[tuple[str, str]] = [
    ("pip_install",     r"\bpip\s+install\s+([a-zA-Z0-9_\-\.]+)"),
    ("git_clone",       r"\bgit\s+clone\s+([^\s]+)"),
    ("npm_install",     r"\bnpm\s+install\s+([a-zA-Z0-9_\-\./@]+)"),
    ("conda_install",   r"\bconda\s+install\s+([a-zA-Z0-9_\-\.]+)"),
    ("url",             r"\bhttps?://[^\s]+"),
    ("clone_repo",      r"\bclone\s+(?:the\s+)?([a-zA-Z0-9_\-\./]+)\s+repo"),
    ("install_package", r"\binstall\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+)\s+package"),
]

# Group 2: Structural / document artifacts.
# These are matched as plain substrings (case-insensitive).
# If found in the lesson text but NOT in the source, the lesson is nulled.
_STRUCTURAL_PATTERNS: list[tuple[str, str]] = [
    ("section_number",   r"\bsection\s+\d+"),           # "Section 3", "Section 4.2"
    ("appendix",         r"\bappendix\b"),
    ("readme",           r"\breadme\b"),
    ("getting_started",  r"\bgetting\s+started\b"),
    ("provided_demo",    r"\bprovided\b"),               # "provided demo", "provided script"
    ("demo",             r"\bdemo\b"),
    ("repo",             r"\brepo\b"),
    # filenames with common code/data extensions (word boundary before name)
    ("filename",         r"\b\w[\w\-]*\.(py|ipynb|sh|yaml|yml|json|csv|txt|toml|cfg|ini)\b"),
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _in_source(term: str, source_text: str, source_text_clean: str) -> bool:
    """Return True if `term` (lowercased) appears in the source text."""
    term_l = term.lower()
    term_clean = re.sub(r"[-_,\.:;/\\]", " ", term_l).strip()
    return term_l in source_text or term_clean in source_text_clean


def _lesson_text(output: "ItemAIOutput") -> str:
    """Concatenate all lesson text fields into a single string for pattern checking."""
    lm = output.learning_module
    if lm is None:
        return ""
    parts: list[str] = []
    for field_val in lm.model_dump().values():
        if isinstance(field_val, str):
            parts.append(field_val)
        elif isinstance(field_val, list):
            parts.extend(str(v) for v in field_val if v)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize_item_output(
    output: "ItemAIOutput",
    source_title: str,
    source_excerpt: str | None,
) -> tuple["ItemAIOutput", str]:
    """
    Validate output.learning_module against raw source text.

    Returns:
        (output, validator_result)
        validator_result is "passed", "nulled", or "skipped".
    """
    if not output.learning_module:
        return output, "skipped"

    lesson = _lesson_text(output)
    if not lesson.strip():
        return output, "skipped"

    source_text = f"{source_title} {source_excerpt or ''}".lower()
    source_text_clean = re.sub(r"[-_,\.:;/\\]", " ", source_text)

    # --- Check group 1: install / URL patterns ---
    for label, pattern in _INSTALL_PATTERNS:
        for match in re.finditer(pattern, lesson, re.IGNORECASE):
            matched_str = match.group(0).lower()
            entity = match.group(1).lower() if match.groups() else matched_str
            if not _in_source(entity, source_text, source_text_clean) and \
               not _in_source(matched_str, source_text, source_text_clean):
                logger.warning(
                    "lesson_nulled pattern=%s matched=%r entity=%r not in source",
                    label, matched_str, entity,
                )
                output.learning_module = None
                return output, "nulled"

    # --- Check group 2: structural / document artifact patterns ---
    for label, pattern in _STRUCTURAL_PATTERNS:
        for match in re.finditer(pattern, lesson, re.IGNORECASE):
            matched_str = match.group(0).lower()
            if not _in_source(matched_str, source_text, source_text_clean):
                logger.warning(
                    "lesson_nulled pattern=%s matched=%r not in source",
                    label, matched_str,
                )
                output.learning_module = None
                return output, "nulled"

    return output, "passed"
