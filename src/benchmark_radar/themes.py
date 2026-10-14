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
from .query_lexicon import (
    BM25_B,
    BM25_K1,
    FIELD_ORDER,
    FIELD_WEIGHTS,
    NAME_MATCH_MULTIPLIERS,
    PHRASE_MULTIPLIER,
    browser_tokenizer_contract,
    search_field_tokens,
)
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
.themes-filter{flex:1 1 15rem}
.themes-filter input{width:100%;padding:.55rem .75rem;border:1px solid var(--ink);
  border-radius:var(--radius-sm);background:var(--canvas,#fff);color:var(--ink);font:inherit}
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
        if not all(isinstance(value, str) and value.strip() for value in (source, key, name, slug)):
            raise ValueError("benchmark index record requires source, key, name and slug")
        identity = (source, key)
        if identity in records:
            raise ValueError(f"duplicate benchmark source record: {identity}")
        categories = item.get("categories", [])
        if not isinstance(categories, list) or any(
            not isinstance(category, str) or not category.strip() for category in categories
        ):
            raise ValueError(f"invalid benchmark categories: {key}")
        field_tokens = search_field_tokens(item)
        records[identity] = {
            "source": source,
            "source_id": key,
            "categories": sorted(set(categories)),
            "title": name,
            "url": f"/benchmarks/{slug}/",
            "date": str(item.get("released") or "")[:10],
            "summary": " ".join(str(item.get("description") or "").split())[:_SUMMARY_CLIP],
            "search_fields": [field_tokens[field] for field in FIELD_ORDER],
            "completeness": sum(
                item.get(field) not in (None, "") for field in ("publisher", "released", "modality")
            )
            + sum(bool(item.get(field)) for field in ("has_paper", "has_repo", "has_dataset")),
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
        f'data-name="{esc(record["title"])}" '
        f'data-categories="{esc(json.dumps(record["categories"], ensure_ascii=False))}" '
        f'data-search-fields="{esc(json.dumps(record["search_fields"], ensure_ascii=False))}" '
        f'data-completeness="{record["completeness"]}">'
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
    search_config = json.dumps(
        {
            "weights": [FIELD_WEIGHTS[field] for field in FIELD_ORDER],
            "k1": BM25_K1,
            "b": BM25_B,
            "nameMultipliers": NAME_MATCH_MULTIPLIERS,
            "phraseMultiplier": PHRASE_MULTIPLIER,
            "tokenizer": browser_tokenizer_contract(),
        },
        ensure_ascii=False,
    )
    body = rf"""{_PAGE_STYLE}
<div class="themes-page">
  <h1>Browse benchmarks by category</h1>
  <p class="themes-lede">Find benchmarks across the full catalog using its existing
  categories. Search by name or choose a category; open any record for scores and sources.</p>
  <p class="themes-lede-zh" lang="zh-Hans">按目录现有分类浏览全部 benchmark；
  未分类、没有分数或发布日期的记录也保留在这里。</p>
  <details class="themes-coverage"><summary>Catalog coverage / 目录覆盖</summary>
    <p class="themes-ledger">{ledger}</p></details>
  <div class="themes-toolbar">
    <label class="themes-filter"><span class="visually-hidden">Search all benchmark records</span>
      <input id="theme-filter" type="search" placeholder="Search all benchmarks…"
        autocomplete="off">
    </label>
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
  const filter = document.getElementById("theme-filter");
  const category = document.getElementById("theme-category");
  const grid = document.querySelector(".theme-grid");
  const cards = Array.from(document.querySelectorAll(".theme-card"));
  const config = {search_config};
  const records = cards.map(card => ({{
    card, categories: JSON.parse(card.dataset.categories),
    fields: JSON.parse(card.dataset.searchFields),
    name: card.dataset.name, key: card.dataset.record,
    completeness: Number(card.dataset.completeness)
  }}));
  // The published fields, weights, and tokenizer come from QueryService's
  // lexical contract, including aliases and untruncated descriptions.
  const sums = Array.from({{length: config.weights.length}}, () => [0, 0]);
  const frequency = new Map();
  const ascii = token => [...token].every(letter => letter.charCodeAt(0) < 128);
  for (const record of records) {{
    record.lengths = [];
    record.counts = record.fields.map((tokens, field) => {{
      const counts = new Map();
      const lengths = [0, 0];
      for (const token of tokens) {{
        counts.set(token, (counts.get(token) || 0) + 1);
        lengths[ascii(token) ? 0 : 1] += 1;
      }}
      record.lengths.push(lengths);
      sums[field][0] += lengths[0];
      sums[field][1] += lengths[1];
      return counts;
    }});
    record.allTokens = new Set(record.fields.flat());
    for (const token of record.allTokens) {{
      frequency.set(token, (frequency.get(token) || 0) + 1);
    }}
  }}
  const average = sums.map(pair => pair.map(total => total / records.length || 1));
  const idf = token => Math.log1p(
    (records.length - (frequency.get(token) || 0) + .5) /
    ((frequency.get(token) || 0) + .5)
  );
  const contains = (haystack, needle) => needle.length <= haystack.length &&
    haystack.some((_, i) => needle.every((part, j) => haystack[i + j] === part));
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  const fold = value => Array.from(value, letter =>
    config.tokenizer.casefold[letter] ?? letter).join("");
  function nfkd(value) {{
    const output = [];
    for (const letter of value) {{
      for (const part of config.tokenizer.nfkd[letter] ?? letter) {{
        const level = config.tokenizer.combining[part] || 0;
        if (!level) {{
          output.push(part);
          continue;
        }}
        let position = output.length;
        while (position && (config.tokenizer.combining[output[position - 1]] || 0) > level) {{
          position--;
        }}
        output.splice(position, 0, part);
      }}
    }}
    return output.join("");
  }}
  function rankedKey(record, query, queryWeight) {{
    const matched = query.filter(token => record.allTokens.has(token));
    if (!matched.length) return null;
    const name = record.fields[0];
    const nameTier = name.length === query.length && contains(name, query) ? 0
      : contains(name.slice(0, query.length), query) ? 1
      : contains(name, query) ? 2 : 3;
    let bm25f = 0;
    for (const token of query) {{
      let weighted = 0;
      for (let field = 0; field < record.fields.length; field++) {{
        const count = record.counts[field].get(token) || 0;
        if (!count) continue;
        const kind = ascii(token) ? 0 : 1;
        const length = record.lengths[field][kind];
        const normalization = 1 - config.b + config.b * length / average[field][kind];
        weighted += config.weights[field] * count / normalization;
      }}
      if (weighted) bm25f += idf(token) * weighted * (config.k1 + 1) / (config.k1 + weighted);
    }}
    const nonNamePhrase = record.fields.slice(1).some(field => contains(field, query));
    const score = bm25f + (nonNamePhrase ? queryWeight * config.phraseMultiplier : 0)
      + (nameTier < 3 ? queryWeight * config.nameMultipliers[nameTier] : 0);
    const coverage = matched.reduce((total, token) => total + idf(token), 0) / queryWeight;
    const tier = nameTier < 3 ? nameTier : matched.length === query.length ? 3 : 4;
    return [-score, -coverage, tier, -record.completeness,
      Array.from(record.name).length, fold(record.name), record.key];
  }}
  function compareKeys(left, right) {{
    for (let i = 0; i < left.length; i++) {{
      const result = compare(left[i], right[i]);
      if (result) return result;
    }}
    return 0;
  }}
  function queryTokens(value) {{
    const normalized = fold(nfkd(value));
    const cjk = config.tokenizer.cjk;
    const latin = config.tokenizer.latinExtended;
    const positive = config.tokenizer.positive;
    const pattern = new RegExp(
      `[a-z0-9]+|(?<cjk>[${{cjk}}]+)|(?:(?![${{cjk}}${{latin}}])[${{positive}}])+`,
      "gu"
    );
    return Array.from(normalized.matchAll(pattern)).flatMap(match => {{
      const part = match[0];
      if (match.groups?.cjk !== undefined) {{
        const letters = Array.from(part.normalize("NFC"));
        return letters.length === 1 ? letters
          : letters.slice(1).map((_, i) => letters[i] + letters[i + 1]);
      }}
      return [part];
    }});
  }}
  function applyFilter() {{
    const rawQuery = filter.value.trim();
    const query = [...new Set(queryTokens(rawQuery))];
    const invalidQuery = rawQuery.length > 0 && query.length === 0;
    const selected = category.value;
    const queryWeight = query.reduce((total, token) => total + idf(token), 0);
    const ranked = query.length ? records.map(record => ({{
      record, key: rankedKey(record, query, queryWeight)
    }})).filter(hit => hit.key).sort((a, b) => compareKeys(a.key, b.key)) : [];
    const matchesQuery = new Set(ranked.map(hit => hit.record));
    const rankedCards = ranked.map(hit => hit.record.card);
    const rankedCardSet = new Set(rankedCards);
    let visible = 0;
    records.forEach(record => {{
      const matchesCategory = !selected || (selected === "__uncategorized__"
        ? record.categories.length === 0 : record.categories.includes(selected));
      const matches = matchesCategory && !invalidQuery &&
        (!query.length || matchesQuery.has(record));
      record.card.classList.toggle("hidden-by-filter", !matches);
      if (matches) visible += 1;
    }});
    // Keep keyboard focus and the accessibility tree in the same rank order
    // as the painted grid. Clearing search restores the original browse order.
    const ordered = query.length
      ? [...rankedCards, ...cards.filter(card => !rankedCardSet.has(card))]
      : cards;
    grid.append(...ordered);
    document.getElementById("theme-results").textContent = invalidQuery
      ? "Enter a search term containing letters or numbers."
      : `Showing ${{visible}} of ${{cards.length}} benchmark records`;
    const empty = document.getElementById("theme-no-results");
    empty.hidden = visible !== 0;
    empty.textContent = invalidQuery
      ? "This search has no searchable letters or numbers."
      : "No benchmarks match these filters.";
  }}
  filter.addEventListener("input", applyFilter);
  category.addEventListener("change", applyFilter);
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
