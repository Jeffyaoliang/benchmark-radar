"""Browse the complete unified benchmark catalog using its existing categories.

Source-native discovery tags remain provenance in the connector; this surface
uses the catalog's categories without creating another taxonomy or population.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .blog_shell import (
    SiteChrome,
    chrome_i18n_table,
    extract_site_chrome,
    render_page,
)
from .catalog import validate_benchmark_index
from .feed import SITE_URL
from .site_shell import breadcrumb_schema, esc, webpage_schema

THEMES_PATH = "/themes/"

_SUMMARY_CLIP = 220

_EMPTY_STATE = "No benchmarks are present in the catalog yet."
_UNTHEMED = "Uncategorized"

_SOURCE_NAMES = {
    "llm_stats": "LLM Stats",
    "model_reports": "Model reports",
    "claire_radar": "Claire Radar",
    "artificial_analysis": "Artificial Analysis",
    "opencompass_hub": "OpenCompass Hub",
}

_PAGE_STYLE = """
<style>
.themes-page{max-width:72rem;margin:0 auto;padding:1.2rem 0 3rem}
.themes-page h1{font-size:clamp(1.5rem,3vw,2rem);margin:.2rem 0 .5rem}
.themes-lede{color:var(--muted);margin:.3rem 0;max-width:52rem}
.themes-lede-zh{color:var(--muted);font-size:.92rem;margin:.2rem 0 0}
.themes-ledger{color:var(--muted);font-size:.85rem;margin:.4rem 0 0}
.themes-toolbar{position:sticky;top:.6rem;z-index:5;display:flex;flex-wrap:wrap;
  gap:.5rem;align-items:center;background:var(--panel);border:1px solid var(--edge);
  border-radius:var(--radius);padding:.7rem .8rem;margin:1.1rem 0 1.3rem;
  box-shadow:0 2px 10px rgba(21,36,42,.06)}
.themes-filter{flex:1 1 15rem;display:flex;gap:.5rem;min-width:0}
.themes-filter input{width:100%;min-width:0;padding:.55rem .75rem;border:1px solid var(--ink);
  border-radius:var(--radius-sm);background:var(--canvas,#fff);color:var(--ink);font:inherit}
.themes-filter button{padding:.55rem .85rem;min-height:44px;font:inherit;cursor:pointer;
  color:var(--ink);background:var(--panel);border:1px solid var(--edge);border-radius:6px}
.themes-category{flex:0 1 20rem;min-width:0}
.themes-category select{max-width:100%;width:100%;padding:.55rem .75rem;font:inherit;
  border:1px solid var(--edge);border-radius:var(--radius-sm);background:var(--panel);
  color:var(--ink)}
.themes-coverage{color:var(--muted);font-size:.85rem;margin:.7rem 0}
.theme-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(19rem,100%),1fr));gap:.7rem}
.theme-card{display:flex;flex-direction:column;gap:.3rem;background:var(--panel);
  border:1px solid var(--edge);border-radius:var(--radius);padding:.75rem .85rem}
.theme-card-title{color:var(--ink);font-weight:600;text-decoration:none;line-height:1.35}
.theme-card-title:hover{text-decoration:underline}
.theme-card-meta{font-size:.78rem;color:var(--muted)}
.theme-card-summary{margin:0;font-size:.87rem}
.themes-empty{background:var(--panel);border:1px solid var(--edge);
  border-radius:var(--radius);padding:1.2rem;margin:1.4rem 0}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap}
.hidden-by-filter{display:none!important}
</style>
"""


def build_theme_index(catalog: dict[str, Any]) -> dict[str, Any]:
    """Keep every source record and group by the categories already in the index.

    Missing dates, scores, descriptions and categories never exclude a record.
    Duplicate source keys, or an index that breaks the shared catalog contract,
    fail instead of publishing a subset.
    """
    rows = validate_benchmark_index(catalog)
    records = {}
    members: dict[str, set[tuple[str, str]]] = {}
    categorized: set[tuple[str, str]] = set()
    source_counts: dict[str, int] = {}
    for item in rows:
        source, key = item.get("source"), item.get("key")
        name, slug = item.get("name"), item.get("slug")
        identity = (source, key)
        categories = item["categories"]
        records[identity] = {
            "source": source,
            "source_id": key,
            "categories": sorted(set(categories)),
            "title": name,
            "url": f"/benchmarks/{slug}/",
            "date": str(item.get("released") or "")[:10],
            "summary": " ".join(str(item.get("description") or "").split())[:_SUMMARY_CLIP],
        }
        source_counts[source] = source_counts.get(source, 0) + 1
        for category in set(categories):
            members.setdefault(category, set()).add(identity)
            categorized.add(identity)

    def ordered(identities):
        return sorted(
            (records[identity] for identity in identities),
            key=lambda row: (row["date"], row["title"], row["source_id"]),
            reverse=True,
        )

    groups = [
        {"category": category, "count": len(identities), "records": ordered(identities)}
        for category, identities in sorted(
            members.items(), key=lambda pair: (-len(pair[1]), pair[0])
        )
    ]
    dates = [row["date"] for row in records.values() if row["date"]]
    return {
        "groups": groups,
        "all_records": ordered(set(records)),
        "unthemed": ordered(set(records) - categorized),
        "records": len(records),
        "tagged": len(categorized),
        "source_counts": dict(sorted(source_counts.items())),
        "updated": max(dates) if dates else None,
    }


def _record_card(record: dict[str, Any]) -> str:
    source_name = _SOURCE_NAMES.get(record["source"], record["source"])
    meta = f"{source_name} · {record['date'] or 'Release date unknown'}"
    summary_text = " ".join(str(record.get("summary") or "").split())[:_SUMMARY_CLIP]
    summary = f'<p class="theme-card-summary">{esc(summary_text)}</p>' if summary_text else ""
    return (
        f'<article class="theme-card" data-record="{esc(record["source_id"])}" '
        f'data-categories="{esc(json.dumps(record["categories"], ensure_ascii=False))}">'
        f'<a class="theme-card-title" href="{esc(record["url"])}">{esc(record["title"])}</a>'
        f'<p class="theme-card-meta">{esc(meta)}</p>'
        f"{summary}"
        f"</article>"
    )


def _themes_page(
    index: dict[str, Any], chrome: SiteChrome, chrome_i18n: dict[str, str]
) -> tuple[str, int]:
    groups = index["groups"]
    options = "".join(
        f'<option value="{esc(group["category"])}">'
        f"{esc(group['category'])} ({group['count']})</option>"
        for group in sorted(groups, key=lambda group: group["category"].casefold())
    )
    if index["unthemed"]:
        options += (
            f'<option value="__uncategorized__">Uncategorized ({len(index["unthemed"])})</option>'
        )
    cards = "".join(_record_card(record) for record in index["all_records"])
    source_ledger = " · ".join(
        f"{_SOURCE_NAMES.get(source, source)}: {count}"
        for source, count in index["source_counts"].items()
    )
    ledger = (
        f"{index['records']} benchmark records across {len(index['source_counts'])} sources: "
        f"{index['tagged']} categorized, {len(index['unthemed'])} uncategorized. "
        "Every source record appears once. Category counts can overlap. "
        f"0 records omitted. {esc(source_ledger)}"
    )
    empty = f'<div class="themes-empty">{esc(_EMPTY_STATE)}</div>' if not index["records"] else ""
    body = rf"""{_PAGE_STYLE}
<div class="themes-page">
  <h1>Browse benchmarks by category</h1>
  <p class="themes-lede">Find benchmarks across the full catalog using its existing
  categories. Choose a category; open any record for scores and sources.</p>
  <p class="themes-lede-zh" lang="zh-Hans">按目录现有分类浏览全部 benchmark；
  未分类、没有分数或发布日期的记录也保留在这里。</p>
  <details class="themes-coverage"><summary>Catalog coverage / 目录覆盖</summary>
    <p class="themes-ledger">{ledger}</p></details>
  <div class="themes-toolbar">
    <form class="themes-filter" action="/saturation/" method="get" role="search">
      <label class="visually-hidden" for="benchmark-query">Search all benchmark records</label>
      <input id="benchmark-query" name="bq" type="search" placeholder="Search all benchmarks…"
        autocomplete="off" required>
      <button type="submit">Search</button>
    </form>
    <label class="themes-category"><span class="visually-hidden">Benchmark category</span>
      <select id="theme-category"><option value="">All categories ({index["records"]})</option>
      {options}</select></label>
  </div>
  <p id="theme-results" role="status">Showing {index["records"]} of
    {index["records"]} benchmark records</p>
  <div class="theme-grid">{cards}</div>
  <p id="theme-no-results" class="themes-empty" hidden>No benchmarks match these filters.</p>
  {empty}
</div>
<script>
(() => {{
  const category = document.getElementById("theme-category");
  const cards = Array.from(document.querySelectorAll(".theme-card"));
  const records = cards.map(card => ({{card, categories: JSON.parse(card.dataset.categories)}}));
  function applyCategory() {{
    let visible = 0;
    for (const record of records) {{
      const show = !category.value || (category.value === "__uncategorized__"
        ? record.categories.length === 0 : record.categories.includes(category.value));
      record.card.classList.toggle("hidden-by-filter", !show);
      if (show) visible++;
    }}
    document.getElementById("theme-results").textContent =
      `Showing ${{visible}} of ${{cards.length}} benchmark records`;
    document.getElementById("theme-no-results").hidden = visible > 0;
  }}
  category.addEventListener("change", applyCategory);
  applyCategory();
}})();
</script>"""
    canonical = f"{SITE_URL}{THEMES_PATH}"
    title = "Browse benchmarks by category | Benchmark Radar"
    description = (
        f"Browse all {index['records']} benchmark records across "
        f"{len(index['source_counts'])} sources by the catalog's existing categories, "
        "including uncategorized records."
    )
    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        body=body,
        chrome=chrome,
        updated=index["updated"],
        chrome_i18n=chrome_i18n,
        schemas=[
            webpage_schema(
                title=title,
                description=description,
                canonical=canonical,
                languages=("en", "zh-Hans"),
            ),
            breadcrumb_schema(
                ("Benchmark Radar", f"{SITE_URL}/"), ("Themes", canonical), canonical=canonical
            ),
        ],
    ), len(index["all_records"])


def load_theme_catalog(site_dir: Path, *, catalog_path: Path | None = None) -> dict[str, Any]:
    """Read and validate the unified catalog a /themes/ build publishes.

    The catalog is gitignored, so a checkout that skipped `normalize-catalog`
    has none. Site builds call this before writing their first page: found
    later, the missing or malformed catalog aborts the rebuild after the
    dashboard, feed and blog are already on disk and leaves a site that
    publishes everything except the section its nav links to.
    """
    path = catalog_path or site_dir / "data" / "benchmark-index.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "the theme browse page is built from the unified catalog, which is "
            f"missing at {path}; run `benchmark-radar normalize-catalog`"
        ) from error
    validate_benchmark_index(catalog)
    return catalog


def write_themes(
    site_dir: Path,
    *,
    catalog_path: Path | None = None,
    dashboard_html: str | None = None,
    app_js: str | None = None,
) -> dict[str, Any]:
    """Write the theme browse page atomically and report what it published.

    The chrome is extracted from the committed dashboard source for the same
    reason the blog's is: one masthead, nav, and footer rather than two
    drifting copies. ``extract_site_chrome`` requires the dashboard footer to
    link ``/themes/``, so a page cannot claim a section the site does not
    have. Tests pass both sources explicitly; the defaults read the committed
    files beside the output directory.
    """
    if dashboard_html is None:
        dashboard_source = site_dir / "index.html"
        if not dashboard_source.is_file():
            raise FileNotFoundError(
                "the themes chrome is extracted from the committed dashboard "
                f"source, which is missing at {dashboard_source}"
            )
        dashboard_html = dashboard_source.read_text(encoding="utf-8")
    if app_js is None:
        app_js_source = site_dir / "assets" / "app.js"
        if not app_js_source.is_file():
            raise FileNotFoundError(
                "the themes chrome translations are baked from the committed "
                f"app.js, which is missing at {app_js_source}"
            )
        app_js = app_js_source.read_text(encoding="utf-8")
    chrome = extract_site_chrome(dashboard_html, active_path=THEMES_PATH)
    chrome_i18n = chrome_i18n_table(chrome, app_js)
    catalog = load_theme_catalog(site_dir, catalog_path=catalog_path)
    index = build_theme_index(catalog)
    page, rendered = _themes_page(index, chrome, chrome_i18n)
    output_dir = site_dir / "themes"
    staging = site_dir / "themes.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "index.html").write_text(page, encoding="utf-8")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)
    return {
        "path": THEMES_PATH,
        "categories": len(index["groups"]),
        "records": index["records"],
        "tagged": index["tagged"],
        "unthemed": len(index["unthemed"]),
        "rendered": rendered,
        "source_counts": index["source_counts"],
        "omitted": 0,
        "sitemap_entries": [(THEMES_PATH, index["updated"])],
    }
