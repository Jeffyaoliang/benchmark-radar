"""Shared lexical fields and tokenizer for catalog query surfaces."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
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
FIELD_WEIGHTS = {
    "name": 5.0,
    "description": 1.0,
    "categories": 2.5,
    "publisher": 0.6,
    "modality": 1.2,
    "languages": 0.3,
    "source": 0.2,
}
BM25_K1 = 1.2
BM25_B = 0.75
NAME_MATCH_MULTIPLIERS = (3.0, 1.5, 0.75)
PHRASE_MULTIPLIER = 0.5

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


@lru_cache(maxsize=1)
def browser_tokenizer_contract() -> dict[str, Any]:
    """Export Python's full case fold and exact token classes to the static page."""
    # JavaScript's Unicode property classes follow the reader's browser, which
    # may recognize letters that this Python runtime does not (or vice versa).
    # Serialize the positive class used by _TOKEN_PARTS as compact codepoint
    # ranges, so both sides agree even across Unicode database versions.
    positive = re.compile(r"[^\W\d_]")
    runs: list[list[int]] = []
    for codepoint in range(0x110000):
        if not positive.fullmatch(chr(codepoint)):
            continue
        if runs and runs[-1][1] + 1 == codepoint:
            runs[-1][1] = codepoint
        else:
            runs.append([codepoint, codepoint])
    positive_ranges = "".join(
        f"\\u{{{start:X}}}" + (f"-\\u{{{end:X}}}" if end != start else "") for start, end in runs
    )
    return {
        "cjk": _CJK_CHARS,
        "latinExtended": _LATIN_EXTENDED,
        "positive": positive_ranges,
        "casefold": {
            char: folded
            for codepoint in range(0x110000)
            if (folded := (char := chr(codepoint)).casefold()) != char
        },
    }
