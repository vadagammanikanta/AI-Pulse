"""Tests for JSON array extraction in llm_router."""
from app.ai.llm_router import _extract_json_array


def test_extract_json_array_handles_markdown_fences_and_trailing_text():
    fenced_input = """Here is the extracted analysis:
```json
[
  {
    "what_is_new": "New AI model",
    "why_it_matters": "Improves efficiency"
  }
]
```
Hope this summary helps! Let me know if you need more details."""

    result = _extract_json_array(fenced_input)
    assert result is not None
    assert len(result) == 1
    assert result[0]["what_is_new"] == "New AI model"


def test_extract_json_array_handles_raw_array():
    raw_input = '[{"title": "Test 1"}, {"title": "Test 2"}]'
    result = _extract_json_array(raw_input)
    assert result is not None
    assert len(result) == 2


def test_extract_json_array_handles_single_object():
    obj_input = '{"title": "Single Item"}'
    result = _extract_json_array(obj_input)
    assert result is not None
    assert len(result) == 1
    assert result[0]["title"] == "Single Item"


def test_extract_json_array_returns_none_on_malformed_json():
    bad_input = "```json\n[{'title': 'Truncated json without closing brace...\n```"
    result = _extract_json_array(bad_input)
    assert result is None
