import json
import re
from pathlib import Path

import pytest

from benchmark_radar.themes import build_theme_index, write_themes

SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DASHBOARD_HTML = (SITE_DIR / "index.html").read_text(encoding="utf-8")
APP_JS = (SITE_DIR / "assets" / "app.js").read_text(encoding="utf-8")


def _item(**overrides):
    item = {
        "source": "llm_stats",
        "key": "llm-stats:agent-bench",
        "slug": "llm-stats-agent-bench",
        "name": "Agent Bench",
        "released": "2026-09-09",
        "description": "A benchmark of agent planning.",
        "categories": ["Agents"],
    }
    item.update(overrides)
    return item


def _catalog(items):
    return {"benchmarks": items, "count": len(items)}


def _write(items, tmp_path):
    path = tmp_path / "benchmark-index.json"
    path.write_text(json.dumps(_catalog(items)), encoding="utf-8")
    return write_themes(tmp_path, catalog_path=path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)


def test_catalog_categories_preserve_all_sources_and_missing_measurements():
    rows = [
        _item(),
        _item(source="model_reports", key="reports:one", slug="reports-one", categories=[]),
        _item(
            source="opencompass", key="oc:one", slug="oc-one", categories=["Agents", "Reasoning"]
        ),
        _item(source="artificial_analysis", key="aa:one", slug="aa-one", released=None),
        _item(source="claire_radar", key="cr:one", slug="cr-one", categories=[], description=None),
    ]
    index = build_theme_index(_catalog(rows))
    assert index["records"] == 5
    assert index["tagged"] == 3
    assert len(index["unthemed"]) == 2
    assert sum(index["source_counts"].values()) == 5
    represented = {
        record["source_id"] for group in index["groups"] for record in group["records"]
    } | {record["source_id"] for record in index["unthemed"]}
    assert represented == {row["key"] for row in rows}
    assert [group["category"] for group in index["groups"]] == ["Agents", "Reasoning"]


def test_source_tags_do_not_replace_catalog_categories():
    index = build_theme_index(_catalog([_item(source_tags=["xbsleepy:planning"])]))
    assert [group["category"] for group in index["groups"]] == ["Agents"]


def test_same_key_from_different_sources_stays_separate():
    rows = [_item(key="shared"), _item(source="model_reports", key="shared", slug="report-shared")]
    index = build_theme_index(_catalog(rows))
    assert index["records"] == 2
    assert index["groups"][0]["count"] == 2


def test_duplicate_source_record_fails_instead_of_silently_reducing_population():
    with pytest.raises(ValueError, match="duplicate"):
        build_theme_index(_catalog([_item(), _item()]))


@pytest.mark.parametrize("catalog", [{}, {"benchmarks": [], "count": 1}, _catalog([{}])])
def test_malformed_catalog_is_not_published(catalog):
    with pytest.raises(ValueError):
        build_theme_index(catalog)


def test_browse_renders_beyond_the_previous_cap_and_searches_entire_catalog(tmp_path):
    rows = [
        _item(key=f"llm-stats:{n}", slug=f"llm-stats-{n}", name=f"Benchmark {n}") for n in range(85)
    ]
    report = _write(rows, tmp_path)
    page = (tmp_path / "themes" / "index.html").read_text()
    assert report["records"] == report["rendered"] == 85
    assert report["omitted"] == 0
    assert page.count('class="theme-card"') == 85
    assert set(re.findall(r'data-record="([^"]+)"', page)) == {row["key"] for row in rows}
    assert "85 benchmark records across 1 sources" in page
    assert "0 records omitted" in page
    assert "Search all benchmarks" in page
    assert "/benchmarks/llm-stats-84/" in page
    assert "daily snapshots" not in page
    assert not (tmp_path / "themes.staging").exists()


def test_uncategorized_records_are_visible_and_unknown_dates_are_labelled(tmp_path):
    report = _write([_item(categories=[], released=None)], tmp_path)
    page = (tmp_path / "themes" / "index.html").read_text()
    assert report["unthemed"] == report["records"] == report["rendered"] == 1
    assert "Uncategorized" in page
    assert "Agent Bench" in page
    assert "Release date unknown" in page
    assert "No benchmarks are present" not in page


def test_category_options_include_multicategory_and_uncategorized_records(tmp_path):
    rows = [
        _item(categories=["Agents", "Reasoning"]),
        _item(key="llm-stats:other", slug="other", categories=[]),
    ]
    report = _write(rows, tmp_path)
    page = (tmp_path / "themes" / "index.html").read_text()
    assert '<option value="Agents">Agents (1)</option>' in page
    assert '<option value="Reasoning">Reasoning (1)</option>' in page
    assert '<option value="__uncategorized__">Uncategorized (1)</option>' in page
    assert report["rendered"] == 2
    assert page.count('data-record="llm-stats:agent-bench"') == 1


def test_missing_catalog_fails_instead_of_falling_back_to_snapshots(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_themes(tmp_path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)
    assert not (tmp_path / "themes" / "index.html").exists()


def test_footer_link_is_required(tmp_path):
    path = tmp_path / "benchmark-index.json"
    path.write_text(json.dumps(_catalog([])))
    linkless = DASHBOARD_HTML.replace('<a href="/themes/" data-i18n="Themes">Themes</a>', "")
    with pytest.raises(ValueError):
        write_themes(tmp_path, catalog_path=path, dashboard_html=linkless, app_js=APP_JS)


def test_generated_page_covers_the_fresh_unified_catalog(tmp_path):
    catalog_path = SITE_DIR / "data" / "benchmark-index.json"
    catalog = json.loads(catalog_path.read_text())
    assert len(catalog["benchmarks"]) >= 1259
    assert len({row["source"] for row in catalog["benchmarks"]}) >= 4
    report = write_themes(
        tmp_path, catalog_path=catalog_path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS
    )
    page = (tmp_path / "themes" / "index.html").read_text()
    assert report["records"] == report["rendered"] == catalog["count"]
    assert sum(report["source_counts"].values()) == catalog["count"]
    assert page.count('class="theme-card"') == catalog["count"]
    assert set(re.findall(r'data-record="([^"]+)"', page)) == {
        row["key"] for row in catalog["benchmarks"]
    }
