"""Shared lexical fields and tokenizer for catalog query surfaces."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

FIELD_ORDER = (
    "name",
    "description",
    "categories",
    "publisher",
    "modality",
    "languages",
    "source",
)

# Han ideographs plus hiragana and katakana, which share unspaced text with Han.
_CJK_CHARS = (
    r"\u3005\u3041-\u309f\u30a1-\u30fa\u30fc-\u30ff\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
)
_LATIN_EXTENDED = r"\u00c0-\u02af\u1e00-\u1eff\u2c60-\u2c7f\ua720-\ua7ff\uab30-\uab6f"
_TOKEN_PARTS = re.compile(
    rf"[a-z0-9]+|(?P<cjk>[{_CJK_CHARS}]+)"
    rf"|(?:(?![{_CJK_CHARS}{_LATIN_EXTENDED}])[^\W\d_])+"
)


def tokens(value: Any) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    result: list[str] = []
    for match in _TOKEN_PARTS.finditer(normalized):
        part = match.group()
        if match.lastgroup == "cjk":
            part = unicodedata.normalize("NFC", part)
            result.extend(part[index : index + 2] for index in range(len(part) - 1))
            if len(part) == 1:
                result.append(part)
        else:
            result.append(part)
    return tuple(result)


def field_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "")


def search_field_tokens(record: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Use the same indexed fields and registered aliases for every surface."""
    result = {field: tokens(field_text(record.get(field))) for field in FIELD_ORDER}
    if record.get("aliases"):
        result["name"] = tokens(
            field_text(record.get("name")) + " " + field_text(record["aliases"])
        )
    return result
