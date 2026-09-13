"""Theme browse page: discovery records grouped by their source taxonomy.

Issue #380 part three. The XBsleepy digest tags each agent-benchmark paper
with capability themes, and ``fetch_xbsleepy`` carries them through as
``xbsleepy:``-prefixed categories. This page turns those tags into a
browsable index: pick a theme, see every tagged record, newest first. The
page renders whatever categories arrive rather than hardcoding a taxonomy,
so another source can join by prefixing its own categories.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .blog_shell import (
    SiteChrome,
    chrome_i18n_table,
    extract_site_chrome,
    render_page,
)
from .feed import SITE_URL
from .site_shell import breadcrumb_schema, esc, webpage_schema

THEMES_PATH = "/themes/"

_SUMMARY_CLIP = 220

_EMPTY_STATE = (
    "No tagged records yet. The theme page fills in as tagged records "
    "arrive in the daily snapshots."
)

_PAGE_STYLE = """
<style>
.themes-hero{max-width:60rem;margin:0 auto;padding:1.5rem 1rem 0}
.themes-lede{margin:.4rem 0}
.themes-lede-zh{color:inherit;opacity:.75;margin:.2rem 0 0}
.themes-filter{display:block;margin:1rem 0 .5rem}
.themes-filter input{width:min(100%,24rem);padding:.45rem .6rem;
  border:1px solid var(--border,#d0d7de);border-radius:.4rem;background:inherit;
  color:inherit;font:inherit}
.theme-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 1.2rem;padding:0}
.theme-chips a{display:inline-block;padding:.2rem .6rem;border:1px solid var(--border,#d0d7de);
  border-radius:999px;text-decoration:none;color:inherit;font-size:.85rem}
.theme-chips a:hover{background:var(--border,#d0d7de)}
.theme-group{max-width:60rem;margin:0 auto 2rem;padding:0 1rem}
.theme-group h2{font-size:1.15rem;margin:0 0 .6rem}
.theme-record{border-top:1px solid var(--border,#d0d7de);padding:.7rem 0}
.theme-record-title{font-weight:600;color:inherit}
.theme-record-meta{margin:.15rem 0;font-size:.82rem;opacity:.7}
.theme-record-summary{margin:0;font-size:.92rem}
.themes-empty{max-width:60rem;margin:2rem auto;padding:0 1rem}
</style>
"""


def _items_of(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    # Schema v1 stored discovery records under "items"; v2 renamed them to
    # "evidence_items". write_blog consumes the same mixed list, so the page
    # must read both instead of assuming one.
    for key in ("evidence_items", "items"):
        value = snapshot.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def build_theme_groups(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group every categorized record across snapshots by its category.

    Returns theme groups sorted by record count then name, each with its
    records newest first. Records without categories are the dashboard's
    job, not this page's.
    """
    groups: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for snapshot in snapshots:
        for item in _items_of(snapshot):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            categories = item.get("categories")
            if not title or not url or not isinstance(categories, list):
                continue
            source_id = str(item.get("source_id") or url)
            published = str(
                item.get("updated_at") or item.get("published_at") or snapshot.get("date") or ""
            )[:10]
            summary = " ".join(str(item.get("summary") or "").split())[:_SUMMARY_CLIP]
            for category in categories:
                tag = str(category).strip()
                if not tag:
                    continue
                key = (tag, source_id)
                if key in seen:
                    continue
                seen.add(key)
                group = groups.setdefault(tag, {"category": tag, "count": 0, "records": []})
                group["records"].append(
                    {
                        "source_id": source_id,
                        "title": title,
                        "url": url,
                        "source": str(item.get("source") or "").strip(),
                        "date": published,
                        "summary": summary,
                    }
                )
                group["count"] += 1
    ordered = sorted(groups.values(), key=lambda group: (-group["count"], group["category"]))
    for group in ordered:
        group["records"].sort(key=lambda record: record["date"], reverse=True)
    return ordered


def _record_card(record: dict[str, Any]) -> str:
    meta = " · ".join(part for part in (record["source"], record["date"]) if part)
    summary = (
        f'<p class="theme-record-summary">{esc(record["summary"])}</p>' if record["summary"] else ""
    )
    return (
        f'<article class="theme-record">'
        f'<a class="theme-record-title" href="{esc(record["url"])}">{esc(record["title"])}</a>'
        f'<p class="theme-record-meta">{esc(meta)}</p>'
        f"{summary}"
        f"</article>"
    )


def _themes_page(
    groups: list[dict[str, Any]],
    chrome: SiteChrome,
    chrome_i18n: dict[str, str],
    updated: str | None,
) -> str:
    total_records = len({row["source_id"] for group in groups for row in group["records"]})
    chips = "".join(
        f'<a href="#theme-{esc(group["category"].replace(":", "-"))}">'
        f'{esc(group["category"])} <span aria-hidden="true">{group["count"]}</span></a>'
        for group in groups
    )
    sections = "".join(
        f'<section class="theme-group" id="theme-{esc(group["category"].replace(":", "-"))}" '
        f'aria-labelledby="theme-{esc(group["category"].replace(":", "-"))}-heading">'
        f'<h2 id="theme-{esc(group["category"].replace(":", "-"))}-heading">'
        f'{esc(group["category"])} <span aria-hidden="true">({group["count"]})</span></h2>'
        + "".join(_record_card(record) for record in group["records"])
        + "</section>"
        for group in groups
    )
    empty = f'<p class="themes-empty">{esc(_EMPTY_STATE)}</p>' if not groups else ""
    body = f"""{_PAGE_STYLE}
<div class="themes-hero">
  <h1>Browse benchmarks by theme</h1>
  <p class="themes-lede">Every discovery record that carries a source taxonomy tag,
  grouped for browsing. Tags arrive from the source that knows the record best —
  the XBsleepy digest's capability themes ride in as <code>xbsleepy:</code>
  categories, and other sources can join the same convention.</p>
  <p class="themes-lede-zh" lang="zh-Hans">按主题浏览带来源标签的记录，标签随来源自带。</p>
  <label class="themes-filter">Filter records
    <input id="theme-filter" type="search" placeholder="Type to filter…"
      autocomplete="off" aria-label="Filter records by title or summary">
  </label>
  <nav class="theme-chips" aria-label="Theme index">{chips}</nav>
</div>
{sections}
{empty}
<script>
(() => {{
  const box = document.getElementById("theme-filter");
  if (!box) return;
  box.addEventListener("input", () => {{
    const query = box.value.trim().toLowerCase();
    document.querySelectorAll(".theme-record").forEach((card) => {{
      card.hidden = Boolean(query) && !card.textContent.toLowerCase().includes(query);
    }});
    document.querySelectorAll(".theme-group").forEach((section) => {{
      const anyVisible = Array.from(section.querySelectorAll(".theme-record"))
        .some((card) => !card.hidden);
      section.hidden = Boolean(query) && !anyVisible;
    }});
  }});
}})();
</script>"""
    canonical = f"{SITE_URL}{THEMES_PATH}"
    schemas = [
        webpage_schema(
            title="Browse benchmarks by theme | Benchmark Radar",
            description="Discovery records grouped by their source taxonomy themes.",
            canonical=canonical,
            languages=("en", "zh-Hans"),
        ),
        breadcrumb_schema(
            ("Benchmark Radar", f"{SITE_URL}/"),
            ("Themes", canonical),
            canonical=canonical,
        ),
    ]
    return render_page(
        title="Browse benchmarks by theme | Benchmark Radar",
        description=(
            "Discovery records grouped by their source taxonomy themes — "
            f"{total_records} records across {len(groups)} themes."
        ),
        canonical=canonical,
        body=body,
        chrome=chrome,
        updated=updated,
        chrome_i18n=chrome_i18n,
        schemas=schemas,
    )


def write_themes(
    snapshots: list[dict[str, Any]],
    site_dir: Path,
    *,
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
    groups = build_theme_groups(snapshots)
    updated = next((group["records"][0]["date"] for group in groups if group["records"]), None)
    page = _themes_page(groups, chrome, chrome_i18n, updated)
    output_dir = site_dir / "themes"
    staging = site_dir / "themes.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "index.html").write_text(page, encoding="utf-8")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)
    total_records = len({row["source_id"] for group in groups for row in group["records"]})
    return {
        "path": THEMES_PATH,
        "categories": len(groups),
        "records": total_records,
        "sitemap_entries": [(THEMES_PATH, updated)],
    }
