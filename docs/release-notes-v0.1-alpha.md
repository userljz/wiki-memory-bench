# Release Notes: v0.1-alpha

`wiki-memory-bench` is a reproducible CLI benchmark harness for Markdown/Wiki-style LLM agent memory.

This alpha release is about protocol, artifacts, and honest baseline reporting. It is not a SOTA claim and it is not a production leaderboard.

## What Works

- Deterministic no-key CLI runs.
- Local run storage under `runs/` with manifest, summary, predictions, and artifacts.
- Built-in deterministic systems: `bm25`, `vector-rag`, `clipwiki`, `full-context-heuristic`, and `full-context-oracle`.
- Optional external adapter path for `basic-memory`.
- Optional LiteLLM answerer / judge paths for credentialed calibration.
- Evidence-aware citation metrics for rows with `expected_source_ids`.

## Benchmark Protocol

- Default runs use deterministic answerers and deterministic judges.
- Optional LLM calibration is manual and kept separate from deterministic alpha results.
- Oracle rows are upper bounds and are excluded from fair non-oracle comparisons.
- `clipwiki --mode full-wiki` is non-oracle; only `clipwiki --mode oracle-curated` may use gold evidence labels.
- Dirty report generation requires `WMB_ALLOW_DIRTY_REPORT=1` and must record the dirty state.

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
- `basic-memory` experimental adapter

## Reports

- Technical report: [`reports/v0.1-alpha-results.md`](../reports/v0.1-alpha-results.md)
- Optional LLM smoke calibration: [`reports/llm-smoke-results.md`](../reports/llm-smoke-results.md)
- Public benchmark slice: [`reports/public-benchmark-alpha.md`](../reports/public-benchmark-alpha.md)

The current technical report records `evaluated_source_commit`, `report_generated_at`, git dirty state, exact commands, environment, dataset source/checksum, system options, answerer/judge mode, oracle/non-oracle labels, and per-system limitations.

## Known Limitations

- Public rows are small alpha slices, not exhaustive experimental sweeps.
- Weak rows remain visible; they are part of the release evidence.
- Citation source metrics depend on source-id availability.
- Some public dataset rows still rely on quote fallback citation behavior.
- Optional LLM rows are provider-dependent calibration, not deterministic benchmark claims.
- This release is not published to PyPI.

## What This Release Does Not Prove

- It does not prove that ClipWiki beats vector RAG.
- It does not prove any system is SOTA.
- It does not cover all memory architectures or production retrieval stacks.
- It does not replace larger human or real-world long-term memory evaluation.

## Reproduce

```bash
uv sync --group dev --extra vector
uv run pytest
WMB_ALLOW_DIRTY_REPORT=1 bash scripts/reproduce_v0_1_alpha.sh
```

For a clean public release artifact, rerun without `WMB_ALLOW_DIRTY_REPORT=1` from a clean release commit.
