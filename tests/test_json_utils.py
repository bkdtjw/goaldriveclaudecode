"""Tests for JSON extraction utilities."""

from goaldriveclaude.utils.json_utils import parse_json_from_llm


def test_parse_json_array_with_prefix_text():
    text = """Here is the plan:\n[
  {\"criteria\": \"a\"},
  {\"criteria\": \"b\"}
]"""

    result = parse_json_from_llm(text)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["criteria"] == "a"


def test_parse_json_object_with_suffix_text():
    text = """Result:\n{\"ok\": true, \"count\": 2}\nDone."""

    result = parse_json_from_llm(text)

    assert isinstance(result, dict)
    assert result["ok"] is True
    assert result["count"] == 2


def test_parse_json_from_code_block_array():
    text = """```json
[
  {\"x\": 1},
  {\"x\": 2}
]
```"""

    result = parse_json_from_llm(text)

    assert isinstance(result, list)
    assert [item["x"] for item in result] == [1, 2]
