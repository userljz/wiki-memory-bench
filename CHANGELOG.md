# Changelog

All notable changes to `wiki-memory-bench` will be documented in this file.

## v0.1.0-alpha

First public alpha release.

### Highlights

- Added a reproducible deterministic benchmark harness for Markdown / Wiki memory systems.
- Added public alpha benchmark reporting for:
  - `synthetic-mini`
  - `synthetic-wiki-memory`
  - `locomo-mc10`
  - `longmemeval-s`
- Added deterministic baselines and reference systems:
  - `bm25`
  - `vector-rag`
  - `clipwiki`
  - `full-context-heuristic`
  - `full-context-oracle` as an explicitly separated oracle upper bound

### Evaluation and Reporting

- Added `reports/v0.1-alpha-results.md` for reproducible release-readiness reporting.
- Added a broader public-dataset alpha slice, now retained as historical context under `reports/historical/public-benchmark-alpha-legacy.md`.
- Added dirty-working-tree protection so public reports are refused unless explicitly overridden.
- Added release-grade regression tests for:
  - release readiness
  - ClipWiki quality
  - synthetic diagnostic integrity
  - report integrity

### Optional LLM Calibration

- Added a manual LLM smoke path:
  - `scripts/reproduce_llm_smoke.sh`
- Added `workflow_dispatch` support for optional LLM smoke evaluation:
  - `.github/workflows/llm-smoke.yml`
- Added documentation for optional LLM evaluation in `docs/llm-evaluation.md`
- Added `reports/llm-smoke-results.md` as an optional, credentialed calibration report separate from deterministic alpha rows

### Caveats

- This is still an alpha release, not a final benchmark release.
- Small-limit rows remain engineering slices, not scientific leaderboard claims.
- Optional LLM smoke remains manual unless run with credentials.
