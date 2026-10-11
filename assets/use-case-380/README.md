# Full-catalog category browser

These screenshots show the production `/themes/` generator after a clean
`normalize-catalog` build. They use the unified `benchmark-index.json`, not a
digest replay or discovery snapshots. The page preserves the catalog's existing
categories without introducing a new taxonomy.

- `themes-page.png`: desktop arrival, 1440 × 900.
- `themes-page-pinned.png`: desktop with the existing `Agents` category selected,
  showing 197 matching source records.
- `themes-page-mobile.png`: mobile arrival, 390 × 844.

All captures use device scale factor 1 and the site's shared design tokens.

The rebuilt catalog contains 3,228 records across five sources: 687 LLM Stats,
25 Artificial Analysis, 1,914 Claire Radar, 141 Model reports, and 461
OpenCompass Hub records. All 3,228 records render once; 3,224 have categories
and four remain visible as uncategorized. Categories overlap; their counts are
not additive. There is no record cap or omitted-record trim.

Browser checks verified the rendered ID set against the complete generated
catalog, category membership, the four uncategorized records, full-catalog
search, no-match feedback, filter reset, and no horizontal overflow or script
errors at either viewport. Every card links to its catalog detail page.
