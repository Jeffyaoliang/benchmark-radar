# About page and search visitors

Issue: [#626](https://github.com/ktwu01/benchmark-radar/issues/626)

The goal is discovery through searches such as “AI benchmark database,” for
researchers and developers choosing benchmarks. These visitors need to understand
what the catalog covers, inspect its sources, and find a useful place to start.

The existing `/about/` page explains the project and links into the catalog.
Its media section collects articles, paper listings, summaries, and community
posts. The author's build log remains with the project's own resources.
These links provide context rather than implying endorsement.

About is the last link in the shared masthead. Its content lives in
`src/benchmark_radar/site_about.py`; the shared navigation lives in
`site/index.html`. The site build generates the published page.

The SEO benefit is a hypothesis, not a measured result. Evaluate search discovery
using non-brand search impressions and clicks, including queries about AI
benchmark databases. An About page supports the visitor's understanding; the
catalog and benchmark pages must answer their actual evaluation questions.
