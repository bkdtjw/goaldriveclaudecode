"""JSON helpers for extracting structured payloads from LLM outputs."""

import json
import re


def parse_json_from_llm(text: str) -> dict | list:
    """Safely parse JSON from mixed LLM output.

    Handles:
    - JSON fenced blocks
    - Extra prose before/after JSON
    - JS style line comments
    - Trailing commas
    """
    # 1) Extract code-fenced content if present.
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    # 2) Normalize common non-JSON artifacts.
    text = re.sub(r"//.*?\n", "\n", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Strip control characters except newlines/tabs
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127))

    stripped = text.strip()

    # 3) Try direct parse first.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 4) Slice out likely JSON region from mixed text.
    first_arr = text.find("[")
    first_obj = text.find("{")

    if first_arr != -1 and (first_obj == -1 or first_arr < first_obj):
        end_arr = text.rfind("]")
        if end_arr != -1 and end_arr > first_arr:
            candidate = text[first_arr : end_arr + 1].strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    if first_obj != -1:
        end_obj = text.rfind("}")
        if end_obj != -1 and end_obj > first_obj:
            candidate = text[first_obj : end_obj + 1].strip()
            return json.loads(candidate)

    # 5) Keep original failure behavior if nothing matched.
    return json.loads(stripped)


def clean_bom(text: str) -> str:
    """Remove UTF-8 BOM if present."""
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def safe_json_loads(text: str, default=None) -> dict | list | None:
    """Safe json.loads returning default on parse failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default
