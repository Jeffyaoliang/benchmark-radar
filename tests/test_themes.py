import json
import re
import shutil
import subprocess
from html import unescape
from pathlib import Path

import pytest

from benchmark_radar.query import (
    QueryError,
    QueryPaths,
    QueryService,
    _build_search_corpus,
    _match,
    _tokens,
)
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
        "languages": [],
        "has_paper": False,
        "has_repo": False,
        "has_dataset": False,
        "has_size": False,
    }
    item.update(overrides)
    return item


def _catalog(items):
    return {"schema_version": 1, "benchmarks": items, "count": len(items)}


def _write(items, tmp_path):
    path = tmp_path / "benchmark-index.json"
    path.write_text(json.dumps(_catalog(items)), encoding="utf-8")
    return write_themes(tmp_path, catalog_path=path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)


def _browser_results(tmp_path, query, category="", *, invalid=False, restore=False):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [
            node,
            str(Path(__file__).with_name("themes_filter_harness.mjs")),
            str(tmp_path / "themes" / "index.html"),
            query,
            category,
            "invalid" if invalid else "restore" if restore else "",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_catalog_categories_preserve_all_sources_and_missing_measurements():
    rows = [
        _item(),
        _item(source="model_reports", key="reports:one", slug="reports-one", categories=[]),
        _item(
            source="opencompass", key="oc:one", slug="oc-one", categories=["Agents", "Reasoning"]
        ),
        _item(source="artificial_analysis", key="aa:one", slug="aa-one", released=None),
        _item(source="claire_radar", key="cr:one", slug="cr-one", categories=[], description=""),
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


def test_browse_search_uses_shared_catalog_tokens_including_registered_aliases(tmp_path):
    rows = [
        _item(name="Humanity's Last Exam", aliases=["HLE"], description="A difficult exam."),
        _item(key="llm-stats:other", slug="other", name="Other benchmark", categories=[]),
    ]
    _write(rows, tmp_path)
    assert _browser_results(tmp_path, "HLE") == ["llm-stats:agent-bench"]
    assert _browser_results(tmp_path, "HLE", "__uncategorized__") == []
    assert _browser_results(tmp_path, "Other", "__uncategorized__") == ["llm-stats:other"]


@pytest.mark.parametrize("query", ["MMLU", "MMLU tasks", "New MMLU", "模型评测"])
def test_browse_search_ranking_matches_query_service(tmp_path, query):
    rows = [
        _item(key="llm-stats:mmlu", slug="mmlu", name="MMLU", released="2023-01-01"),
        _item(
            key="llm-stats:mmlu-extended",
            slug="mmlu-extended",
            name="New MMLU Extended",
            released="2026-09-09",
            description="MMLU tasks and MMLU scoring.",
        ),
        _item(
            key="llm-stats:other",
            slug="other",
            name="Other benchmark",
            description="多语言模型评测。",
        ),
    ]
    _write(rows, tmp_path)
    corpus = _build_search_corpus(rows)
    query_tokens = _tokens(query)
    expected = sorted(
        (match[0], doc.record["key"])
        for doc in corpus.documents
        if (match := _match(doc, query_tokens=query_tokens, corpus=corpus)) is not None
    )
    assert _browser_results(tmp_path, query) == [key for _, key in expected]
    if query == "MMLU":
        assert _browser_results(tmp_path, query)[0] == "llm-stats:mmlu"


def test_browse_search_matches_query_service_unicode_casefold_and_latin_ranges(tmp_path):
    rows = [
        _item(key="llm-stats:strasse", slug="strasse", name="Straße"),
        _item(key="llm-stats:lodz", slug="lodz", name="Łódź"),
        _item(key="llm-stats:orsted", slug="orsted", name="Ørsted"),
    ]
    _write(rows, tmp_path)
    corpus = _build_search_corpus(rows)
    for query in ("Straße", "STRASSE", "Łódź", "Ørsted"):
        query_tokens = _tokens(query)
        expected = sorted(
            (match[0], doc.record["key"])
            for doc in corpus.documents
            if (match := _match(doc, query_tokens=query_tokens, corpus=corpus)) is not None
        )
        assert _browser_results(tmp_path, query) == [key for _, key in expected]


def test_browse_does_not_treat_tokenless_input_as_an_empty_search(tmp_path):
    _write([_item()], tmp_path)
    for query in ("!!!", "😀", "Ł", "\U00011db0", "\ua7f1"):
        assert _tokens(query) == ()
        assert _browser_results(tmp_path, query, invalid=True) == []
    assert _browser_results(tmp_path, "") == ["llm-stats:agent-bench"]


def test_browse_restores_dom_order_after_ranked_search(tmp_path):
    rows = [
        _item(key="llm-stats:mmlu", slug="mmlu", name="MMLU", released="2023-01-01"),
        _item(key="llm-stats:new", slug="new", name="New MMLU", released="2026-09-09"),
    ]
    _write(rows, tmp_path)
    assert _browser_results(tmp_path, "MMLU") == ["llm-stats:mmlu", "llm-stats:new"]
    assert _browser_results(tmp_path, "MMLU", restore=True) == [
        "llm-stats:new",
        "llm-stats:mmlu",
    ]


def test_similar_names_from_different_sources_stay_separate():
    rows = [
        _item(key="shared"),
        _item(source="model_reports", key="reports:shared", slug="report-shared"),
    ]
    index = build_theme_index(_catalog(rows))
    assert index["records"] == 2
    assert index["groups"][0]["count"] == 2


def test_duplicate_source_record_fails_instead_of_silently_reducing_population():
    with pytest.raises(ValueError, match="duplicate"):
        build_theme_index(_catalog([_item(), _item()]))


@pytest.mark.parametrize(
    "catalog",
    [
        {},
        {"benchmarks": [], "count": 1},
        {"schema_version": 1, "benchmarks": [_item()]},
        _catalog([{}]),
    ],
)
def test_malformed_catalog_is_not_published(catalog):
    with pytest.raises(ValueError):
        build_theme_index(catalog)


def test_a_schema_the_query_service_rejects_is_not_rendered_as_a_theme_page(tmp_path):
    # Regression: /themes/ checked only `benchmarks`, so a migrated schema the
    # query service refused still rendered -- every card silently Uncategorized.
    migrated = _catalog([_item()]) | {"schema_version": 2}
    del migrated["benchmarks"][0]["categories"]
    path = tmp_path / "benchmark-index.json"
    path.write_text(json.dumps(migrated), encoding="utf-8")

    with pytest.raises(QueryError) as query_error:
        QueryService(QueryPaths(index=path, shards=tmp_path)).search("agent", scope="catalog")
    assert query_error.value.code == "unsupported_schema"
    with pytest.raises(ValueError, match="schema 2 is unsupported"):
        write_themes(tmp_path, catalog_path=path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)
    assert not (tmp_path / "themes" / "index.html").exists()


def test_browse_renders_beyond_the_previous_cap_and_searches_entire_catalog(tmp_path):
    rows = [
        _item(key=f"llm-stats:{n}", slug=f"llm-stats-{n}", name=f"Benchmark {n}") for n in range(85)
    ]
    report = _write(rows, tmp_path)
    page = (tmp_path / "themes" / "index.html").read_text()
    assert report["records"] == report["rendered"] == 85
    assert report["omitted"] == 0
    assert page.count('class="theme-card"') == 85
    assert {unescape(key) for key in re.findall(r'data-record="([^"]+)"', page)} == {
        row["key"] for row in rows
    }
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
    assert {unescape(key) for key in re.findall(r'data-record="([^"]+)"', page)} == {
        row["key"] for row in catalog["benchmarks"]
    }


@pytest.mark.parametrize("query", ["MMLU", "HLE", "agent coding", "模型评测"])
def test_generated_page_uses_query_service_order_on_the_complete_catalog(tmp_path, query):
    catalog_path = SITE_DIR / "data" / "benchmark-index.json"
    write_themes(tmp_path, catalog_path=catalog_path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)
    browser = _browser_results(tmp_path, query)
    service = QueryService(
        QueryPaths(index=catalog_path, shards=catalog_path.parent / "benchmarks")
    ).search(query, scope="catalog", limit=200)
    assert len(browser) == service["candidate_count"]
    assert browser[:20] == [item["key"] for item in service["results"][:20]]


@pytest.mark.parametrize(
    "names,keys",
    [
        (["😀 A", "Ａ A"], ["one", "two"]),
        (["Same", "Same"], ["😀", "Ａ"]),
    ],
)
def test_search_string_ties_use_python_code_point_order(tmp_path, names, keys):
    rows = [
        _item(name=name, key=key, slug=f"record-{i}", description="shared target")
        for i, (name, key) in enumerate(zip(names, keys, strict=True))
    ]
    _write(rows, tmp_path)
    path = tmp_path / "benchmark-index.json"
    results = QueryService(QueryPaths(index=path, shards=tmp_path)).search(
        "target", scope="catalog"
    )
    assert _browser_results(tmp_path, "target") == [row["key"] for row in results["results"]]


@pytest.mark.parametrize(
    "rows",
    [
        [{}],
        *[
            [{key: value for key, value in _item().items() if key != field}]
            for field in (
                "key",
                "slug",
                "name",
                "source",
                "description",
                "categories",
                "languages",
                "has_paper",
                "has_repo",
                "has_dataset",
                "has_size",
            )
        ],
        [_item(categories=[""])],
        [_item(languages=[None])],
        [_item(has_paper=1)],
        [_item(), _item(slug="other")],
        [_item(), _item(key="other")],
    ],
)
def test_invalid_records_fail_all_readers_before_site_output(tmp_path, rows):
    from benchmark_radar.snapshots import rebuild_dashboard

    site = tmp_path / "site"
    data = site / "data"
    data.mkdir(parents=True)
    path = data / "benchmark-index.json"
    path.write_text(json.dumps(_catalog(rows)), encoding="utf-8")
    with pytest.raises(QueryError) as error:
        QueryService(QueryPaths(index=path, shards=tmp_path)).search("agent", scope="catalog")
    assert error.value.code == "invalid_data"
    with pytest.raises(ValueError):
        write_themes(site, catalog_path=path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)
    with pytest.raises(ValueError):
        rebuild_dashboard(
            tmp_path / "snapshots", data / "radar.json", feed_output=site / "feed.xml"
        )
    assert {item.relative_to(site).as_posix() for item in site.rglob("*") if item.is_file()} == {
        "data/benchmark-index.json"
    }
