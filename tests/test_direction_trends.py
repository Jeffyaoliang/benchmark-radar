"""Trends' research-direction table (#420): one computation, two languages."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_seeds import (
    _direction_trends_seed,
    direction_focus_chart,
    direction_sparkline,
)
from benchmark_radar.library_directions import (
    DIRECTION_RANKED,
    direction_display,
    direction_focus_id,
    direction_focus_records,
    direction_trend_rows,
    discovery_anchor,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "site" / "data" / "benchmark-index.json"
TAXONOMY = {
    "groups": [{"id": "g", "name": "Group"}],
    "categories": [
        {"id": "math", "group": "g", "name": "Math"},
        {"id": "science", "group": "g", "name": "Science"},
    ],
}


def record(released, categories=None, source="claire_radar", collected_at="2026-10-14T09:44:51Z"):
    return {
        "name": f"{released} {' '.join(categories or [])}",
        "slug": f"r-{released}",
        "released": released,
        "source": source,
        "collected_at": collected_at,
        "library_direction": {"primary": categories[0], "categories": categories}
        if categories
        else None,
    }


def site_rows(records, taxonomy, anchor, windows):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "tests/direction_trends_harness.mjs"],
        input=json.dumps(
            {"records": records, "taxonomy": taxonomy, "anchor": anchor, "windows": windows}
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    return json.loads(completed.stdout)["models"]


def site_views(records, taxonomy, anchor, windows):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "tests/direction_trends_harness.mjs"],
        input=json.dumps(
            {"records": records, "taxonomy": taxonomy, "anchor": anchor, "windows": windows}
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    payload = json.loads(completed.stdout)
    return payload["views"], payload["focus"]


def python_views(records, taxonomy, anchor, windows):
    views, focus = [], []
    for days in windows:
        model = direction_trend_rows(records, taxonomy, anchor, days)
        per_group = []
        for group in ["", DIRECTION_RANKED, *(entry["id"] for entry in taxonomy["groups"])]:
            lines = direction_display(model, taxonomy, group)
            shown = [line["row"]["id"] for line in lines if "row" in line]
            per_group.append(
                {
                    "group": group,
                    "lines": [
                        line["row"]["id"]
                        if "row" in line
                        else f"# {line['heading']} {line['count']}"
                        for line in lines
                    ],
                    "focus": direction_focus_id(model, shown),
                }
            )
        views.append(per_group)
        focus.append(
            {
                row["id"]: [
                    r["name"] for r in direction_focus_records(records, row["id"], anchor, days)
                ]
                for row in model["rows"]
            }
        )
    return views, focus


def site_anchor(records):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "tests/direction_trends_harness.mjs"],
        input=json.dumps(
            {"records": records, "taxonomy": TAXONOMY, "anchor": "2026-10-14", "windows": []}
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    return json.loads(completed.stdout)["anchor"]


def as_python(model):
    return {
        "anchor": model["anchor"],
        "window_days": model["windowDays"],
        "discovery_since": model["discoverySince"],
        "comparable": model["comparable"],
        "rows": model["rows"],
    }


def test_windows_count_secondary_directions_and_unclassified_records():
    records = [
        record("2026-10-14", ["math", "science"]),
        record("2026-09-20", ["math"]),
        record("2026-10-01"),
        record("2026-05-01", ["math"]),
        record("2026-10-20", ["math"]),  # after the anchor: not yet released
    ]
    model = direction_trend_rows(records, TAXONOMY, "2026-10-14", 30)
    rows = {row["id"]: row for row in model["rows"]}
    assert model["discovery_since"] == "2026-05-01"
    assert rows["math"]["current"] == 2
    assert rows["science"]["current"] == 1
    assert rows["unclassified"]["current"] == 1
    assert model["rows"][-1]["id"] == "unclassified"
    assert rows["math"]["weekly"][-1] == 1


def test_no_comparison_or_bar_before_the_discovery_stream_starts():
    # A previous window that starts before the stream would undercount and
    # fake growth, so it is absent rather than zero.
    records = [record("2026-09-01", ["math"]), record("2026-10-10", ["math"])]
    model = direction_trend_rows(records, TAXONOMY, "2026-10-14", 30)
    rows = {row["id"]: row for row in model["rows"]}
    assert model["comparable"] is False
    assert rows["math"]["previous"] is None
    assert rows["math"]["weekly"][0] is None
    assert rows["math"]["weekly"][-1] == 1


def test_site_and_python_agree_on_rule_cases():
    records = [
        record("2026-10-14", ["math", "science"]),
        record("2026-09-20", ["math"]),
        record("2026-10-01"),
        record("2026-05-01", ["math"]),
        record("2026-01-01", ["science"], source="opencompass_hub"),
    ]
    for model in site_rows(records, TAXONOMY, "2026-10-14", [30, 60, 90]):
        assert as_python(model) == direction_trend_rows(
            records, TAXONOMY, "2026-10-14", model["windowDays"]
        )


@pytest.mark.skipif(not INDEX.exists(), reason="build the data release first")
def test_site_and_python_agree_on_the_published_catalog():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    taxonomy = index["library_taxonomy"]
    anchor = discovery_anchor(index["benchmarks"])
    assert site_anchor(index["benchmarks"]) == anchor
    for model in site_rows(index["benchmarks"], taxonomy, anchor, [30, 60, 90]):
        assert as_python(model) == direction_trend_rows(
            index["benchmarks"], taxonomy, anchor, model["windowDays"]
        )


def test_seed_shows_the_section_with_default_window_rows():
    seeds = _direction_trends_seed({}, [record("2026-10-10", ["math"])], TAXONOMY)
    note, section, body, panel = seeds.values()
    # The caveats travel with the seeded numbers.
    assert "30 days to Oct 14, 2026" in note
    assert "rows overlap and do not add up" in note
    assert "hidden" not in section
    assert '<a href="/library/?dir=math" data-direction="math">Math</a>' in body
    # Grouped, and the top direction is focused in the seeded panel.
    assert '<tr class="direction-group"><th colspan="7">Group' in body
    assert '<tr class="is-focused">' in body
    # The panel's chart values are text for screen readers too.
    # Values the page can re-announce in the reader's language.
    assert '<span class="visually-hidden" data-weekly="' in panel
    assert "Weekly new records, oldest first:" in panel
    assert (
        "Direction focus" in panel
        and '<h3 id="direction-focus-heading" tabindex="-1">Math</h3>' in panel
    )
    # The page ships the 30-day window; its menus wait for live data.
    template = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert 'data-i18n-aria="Window" disabled' in template
    assert 'data-i18n-aria="Group" disabled><option value="" data-i18n="All groups">' in template
    # The sixteen weekly values are text for screen readers, and bars for
    # everyone, as the live renderer draws them.
    # Values the page can re-announce in the reader's language.
    assert '<span class="visually-hidden" data-weekly="' in body
    assert "Weekly new records, oldest first:" in body
    assert '<svg viewBox="0 0 96 20" class="direction-spark" aria-hidden="true">' in body
    # Without a discovery crawl there is no window to anchor.
    assert _direction_trends_seed({}, [record("2026-10-10", ["math"], source="x")], TAXONOMY) == {}


def test_undated_records_are_counted_not_dropped():
    model = direction_trend_rows(
        [record(None, ["math"]), record("2026-10-10", ["math"])], TAXONOMY, "2026-10-14", 30
    )
    math = next(row for row in model["rows"] if row["id"] == "math")
    assert (math["current"], math["undated"]) == (1, 1)


def test_windows_end_at_the_discovery_crawl_not_the_daily_run():
    # The radar advances daily while the catalog stays pinned to its crawl;
    # anchoring to the crawl keeps windows from sliding over unchanged data.
    records = [
        record("2026-10-10", ["math"], collected_at="2026-10-14T09:44:51Z"),
        record("2026-05-20", ["math"], collected_at="2026-09-25T04:40:22Z"),
        record("2026-10-01", ["math"], source="llm_stats", collected_at="2026-10-30T00:00:00Z"),
    ]
    assert discovery_anchor(records) == "2026-10-14"
    assert site_anchor(records) == "2026-10-14"


def test_seeded_bars_and_failure_handling_match_the_page():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    cases = [[0, 3, None, 12, 1, 0, 7, 4, 2, 0, 9, 5, 0, 1, 6, 2], [None] * 16, [0] * 16]
    result = subprocess.run(
        [node, "tests/direction_trends_render_harness.mjs"],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
        cwd=ROOT,
    )
    output = json.loads(result.stdout)
    assert output["sparklines"] == [direction_sparkline(weekly) for weekly in cases]
    assert output["focusCharts"] == [direction_focus_chart(weekly) for weekly in cases]


def test_site_and_python_agree_on_grouping_and_focus():
    taxonomy = {
        "groups": [{"id": "g", "name": "Group"}, {"id": "h", "name": "Other group"}],
        "categories": [
            {"id": "math", "group": "g", "name": "Math"},
            {"id": "science", "group": "g", "name": "Science"},
            {"id": "law", "group": "h", "name": "Law"},
        ],
    }
    records = [
        record("2026-10-14", ["math", "science"]),
        record("2026-10-12", ["law"]),
        record("2026-10-12", ["law", "math"]),
        record("2026-09-20", ["math"]),
        record("2026-10-01"),
    ]
    views, focus = python_views(records, taxonomy, "2026-10-14", [30, 60])
    assert site_views(records, taxonomy, "2026-10-14", [30, 60]) == (views, focus)
    # Grouped by default: each group heads its directions; unclassified last.
    assert views[0][0]["lines"] == [
        "# Group 2",
        "math",
        "science",
        "# Other group 1",
        "law",
        "unclassified",
    ]
    assert views[0][0]["focus"] == "math"
    # Newest first, then by name; only records in the window.
    assert focus[0]["math"] == ["2026-10-14 math science", "2026-10-12 law math", "2026-09-20 math"]


@pytest.mark.skipif(not INDEX.exists(), reason="build the data release first")
def test_site_and_python_agree_on_grouping_and_focus_for_the_published_catalog():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    taxonomy = index["library_taxonomy"]
    anchor = discovery_anchor(index["benchmarks"])
    assert site_views(index["benchmarks"], taxonomy, anchor, [30]) == python_views(
        index["benchmarks"], taxonomy, anchor, [30]
    )


def test_star_growth_counts_each_repository_once_per_direction():
    def starred(released, categories, gain, source_record, repository=None, source="claire_radar"):
        row = record(released, categories, source=source)
        row["attention_signals"] = {
            "github_stars_30d": gain,
            "source_record": source_record,
            "repository": repository,
        }
        return row

    records = [
        # One .com observation reaching two catalog records (DeepSWE through
        # Claire Radar and LLM Stats) counts once.
        starred("2026-10-10", ["math"], 157, "bm_deepswe", source="claire_radar"),
        starred("2026-10-10", ["math"], 157, "bm_deepswe", source="llm_stats"),
        # Two distinct benchmarks sharing one repository count once.
        starred("2026-10-09", ["math"], 72, "bm_a", repository="gh:org/shared"),
        starred("2026-10-08", ["math", "science"], 72, "bm_b", repository="gh:org/shared"),
        starred("2026-10-07", ["math"], -5, "bm_c", repository="gh:org/other"),
    ]
    model = direction_trend_rows(records, TAXONOMY, "2026-10-14", 30)
    math = next(row for row in model["rows"] if row["id"] == "math")
    science = next(row for row in model["rows"] if row["id"] == "science")
    assert (math["stars_30d"], math["stars_tracked"]) == (157 + 72 - 5, 3)
    assert (science["stars_30d"], science["stars_tracked"]) == (72, 1)
    # Every record is still counted as a record.
    assert math["current"] == 5
    # The page computes the same rows.
    for site_model in site_rows(records, TAXONOMY, "2026-10-14", [30]):
        assert as_python(site_model) == model
