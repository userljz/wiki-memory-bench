# Release Notes: v0.1.0-alpha

`wiki-memory-bench` is a benchmark and evaluation harness for Markdown/Wiki memory systems used by LLM agents.

This first public alpha focuses on reproducibility, transparent reporting, and engineering-oriented diagnostics rather than benchmark marketing.

## What Works

- Deterministic benchmark execution through the CLI
- Saved run artifacts under `runs/`
- Reproducible alpha report generation
- Public deterministic slices on:
  - `synthetic-mini`
  - `synthetic-wiki-memory`
  - `locomo-mc10`
  - `longmemeval-s`
- Baselines and systems:
  - `bm25`
  - `vector-rag`
  - `clipwiki`
  - `full-context-heuristic`
  - `full-context-oracle` as a clearly separated oracle upper bound

## What Is Still Alpha

- Public benchmark coverage is still narrow
- Some rows are small-limit slices rather than full experimental sweeps
- Optional LLM smoke evaluation exists, but it is manual and credential-gated
- A credentialed OpenRouter smoke report is available as optional calibration, not as a leaderboard
- Weak rows remain visible because hiding them would reduce benchmark credibility

## Supported Datasets

- `synthetic-mini`
- `synthetic-wiki-memory`
- `locomo-mc10`
- `longmemeval-s`
- `longmemeval-m`
- `longmemeval-oracle`

## Supported Systems

- `bm25`
- `vector-rag`
- `clipwiki`
- `full-context-heuristic`
- `full-context-oracle`
- experimental external adapters such as `basic-memory`

## How To Reproduce

Deterministic alpha snapshot:

```bash
uv sync --group dev --extra vector
uv run pytest -vv
./scripts/reproduce_v0_1_alpha.sh
```

Optional LLM smoke calibration:

```bash
uv sync --group dev --extra llm --extra vector
export WMB_RUN_LLM_INTEGRATION=1
export LLM_MODEL="your-model"
export LLM_API_KEY="your-api-key"
./scripts/reproduce_llm_smoke.sh
```

## Public Reports

- Release report: `reports/v0.1-alpha-results.md`
- Legacy public benchmark slice: `reports/historical/public-benchmark-alpha-legacy.md`
- Optional LLM smoke calibration: `reports/llm-smoke-results.md`

## Known Limitations

- This release does not claim benchmark leadership.
- No oracle row is included in the main non-oracle table.
- `locomo-mc10` remains difficult for all non-oracle deterministic baselines in the current slice.
- Optional LLM smoke rows are provider-dependent calibration results and are not final leaderboard claims.
- This release is not published to PyPI.

## GitHub Release Draft

Use this body for the GitHub release tagged `v0.1.0-alpha`:

```markdown
# v0.1.0-alpha

`wiki-memory-bench` is a benchmark and evaluation harness for Markdown/Wiki memory systems used by LLM agents.

This first public alpha focuses on reproducibility, transparent reporting, and engineering-oriented diagnostics rather than benchmark marketing.

## What Works

- Deterministic benchmark execution through the CLI
- Saved run artifacts under `runs/`
- Reproducible alpha report generation
- Deterministic public slices for `synthetic-mini`, `synthetic-wiki-memory`, and `locomo-mc10`
- Optional manual LLM smoke calibration with deterministic judging
- Baselines and systems: `bm25`, `vector-rag`, `clipwiki`, `full-context-heuristic`, and `full-context-oracle`

## What Is Alpha

- Public benchmark coverage is still narrow
- Some rows are small-limit engineering slices rather than full experimental sweeps
- Weak public rows remain visible on purpose
- Optional LLM smoke rows are provider-dependent calibration results, not leaderboard results
- No SOTA claim is made for ClipWiki or any other system

## Supported Datasets

- `synthetic-mini`
- `synthetic-wiki-memory`
- `locomo-mc10`
- `longmemeval-s`
- `longmemeval-m`
- `longmemeval-oracle`

## Supported Systems

- `bm25`
- `vector-rag`
- `clipwiki`
- `full-context-heuristic`
- `full-context-oracle`
- experimental external adapters such as `basic-memory`

## How To Reproduce

```bash
uv sync --group dev --extra vector
uv run pytest -vv
./scripts/reproduce_v0_1_alpha.sh
```

Optional LLM smoke calibration:

```bash
uv sync --group dev --extra llm --extra vector
export WMB_RUN_LLM_INTEGRATION=1
export LLM_MODEL="your-model"
export LLM_API_KEY="your-api-key"
./scripts/reproduce_llm_smoke.sh
```

## Reports

- Deterministic alpha report: [`reports/v0.1-alpha-results.md`](reports/v0.1-alpha-results.md)
- Legacy public benchmark slice: [`reports/historical/public-benchmark-alpha-legacy.md`](../../reports/historical/public-benchmark-alpha-legacy.md)
- Optional LLM smoke report: [`reports/llm-smoke-results.md`](reports/llm-smoke-results.md)

## Known Limitations

- This release does not claim benchmark leadership.
- No oracle row is included in the main non-oracle table.
- `locomo-mc10` remains difficult for all non-oracle deterministic baselines in the current slice.
- Optional LLM smoke rows are manual calibration results.
- This release is not published to PyPI.
```
