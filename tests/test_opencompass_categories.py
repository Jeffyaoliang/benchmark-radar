"""OpenCompass online-eval status is not a topic the benchmark evaluates."""

from __future__ import annotations

# The hub writes this pair on benchmarks it does not host for online evaluation.
# Readers were told those benchmarks evaluate "Unsupported".
_STATUS_TAGS = frozenset({"不支持", "unsupported"})


def test_opencompass_online_eval_status_is_not_a_category() -> None:
    from benchmark_radar.catalog_opencompass import normalize_opencompass

    records = normalize_opencompass()["source_records"]
    # Dropping the status tag must not drop the benchmark or its real topics.
    assert len(records) == 461
    labelled = [
        record["name"]
        for record in records
        if any(str(category).casefold() in _STATUS_TAGS for category in record["categories"])
    ]
    assert labelled == []
    assert all(record["categories"] for record in records)

    toxicity = next(record for record in records if record["name"] == "RealToxicityPrompts")
    assert "Safety" in toxicity["categories"]
    assert "安全" in toxicity["categories"]
    assert "LLM" in toxicity["categories"]
    assert "Safety Alignment" in toxicity["categories"]
