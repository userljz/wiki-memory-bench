# Public Benchmark Alpha Legacy

Historical alpha report generated before v0.1 fairness/citation metric updates. Do not use for current comparisons.

This report is an engineering-focused public benchmark slice for `wiki-memory-bench`.

It is intended to strengthen the public benchmark story beyond `synthetic-wiki-memory` by using public datasets and by keeping weak rows visible.

## Scope

- commit: `7e4b0584fbf1aeeb6960d9b94c60cef16ad7f51b`
- execution style: deterministic public alpha slice
- benchmark host: clean local clone of the target commit
- Python: `3.11.15`
- uv: `0.11.7`
- vector dependency installed: `true`
- LLM environment configured locally: `false`

## Caveat

These are alpha slices, not final scientific leaderboard claims.

- `locomo-mc10` rows below use `--limit 100`
- `longmemeval-s` rows below use `--limit 20`
- weak rows are intentionally retained
- oracle rows are separated from the main non-oracle table
- this legacy report uses the old `Citation Precision` column, not the current evidence-aware citation source metrics

## Exact Commands

Deterministic rows that were executed:

```bash
uv run wmb run --dataset locomo-mc10 --system bm25 --limit 100
uv run wmb run --dataset locomo-mc10 --system vector-rag --limit 100
uv run wmb run --dataset locomo-mc10 --system clipwiki --mode full-wiki --limit 100
uv run wmb run --dataset locomo-mc10 --system clipwiki --mode curated --limit 100
uv run wmb run --dataset locomo-mc10 --system full-context-heuristic --limit 100
uv run wmb run --dataset locomo-mc10 --system full-context-oracle --limit 100
uv run wmb run --dataset longmemeval-s --system bm25 --limit 20
uv run wmb run --dataset longmemeval-s --system clipwiki --limit 20
```

LLM rows requested for this report but not executed locally:

```bash
uv run wmb run --dataset locomo-mc10 --system bm25 --answerer llm --judge deterministic --limit 50
uv run wmb run --dataset locomo-mc10 --system vector-rag --answerer llm --judge deterministic --limit 50
uv run wmb run --dataset locomo-mc10 --system clipwiki --answerer llm --judge deterministic --limit 50
uv run wmb run --dataset longmemeval-s --system bm25 --answerer llm --judge llm --limit 20
uv run wmb run --dataset longmemeval-s --system clipwiki --answerer llm --judge llm --limit 20
```

## Deterministic Non-Oracle Rows

| Dataset | System | Mode | Limit | Accuracy | Citation Precision (legacy) | Avg Latency (ms) | Avg Retrieved Tokens | Run ID | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `locomo-mc10` | `bm25` | default | 100 | 33.00% | 13.00% | 2.94 | 2255.96 | `20260420T144530Z-locomo-mc10-bm25` | Cheap lexical baseline; strongest deterministic non-oracle public row in this slice. |
| `locomo-mc10` | `vector-rag` | default | 100 | 23.00% | 8.00% | 494.62 | 852.99 | `20260420T144529Z-locomo-mc10-vector-rag` | Lower retrieved token count, but weaker answer accuracy on this slice. |
| `locomo-mc10` | `clipwiki` | `full-wiki` | 100 | 32.00% | 10.00% | 16.58 | 1801.38 | `20260420T144530Z-locomo-mc10-clipwiki` | Non-oracle wiki retrieval with full compilation. |
| `locomo-mc10` | `clipwiki` | `curated` | 100 | 33.00% | 11.00% | 5.71 | 1874.25 | `20260420T144749Z-locomo-mc10-clipwiki` | Heuristic curated mode; no gold labels were used on this dataset. |
| `locomo-mc10` | `full-context-heuristic` | default | 100 | 38.00% | 18.00% | 23.12 | 14955.00 | `20260420T144749Z-locomo-mc10-full-context-heuristic` | Useful non-oracle upper reference, but not a deployable retrieval baseline. |
| `longmemeval-s` | `bm25` | default | 20 | 55.00% | 75.00% | 13.65 | 9639.45 | `20260420T144804Z-longmemeval-s-bm25` | Small public open-QA slice; still only an alpha sample. |
| `longmemeval-s` | `clipwiki` | `full-wiki` | 20 | 50.00% | 75.00% | 89.18 | 6531.45 | `20260420T144804Z-longmemeval-s-clipwiki` | Lower retrieved token count than BM25, but slightly lower answer accuracy in this slice. |

## Oracle Rows

These rows are intentionally excluded from the main non-oracle table.

| Dataset | System | Limit | Accuracy | Citation Precision (legacy) | Avg Latency (ms) | Avg Retrieved Tokens | Run ID | Why It Is Separate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `locomo-mc10` | `full-context-oracle` | 100 | 100.00% | 18.00% | 24.27 | 14955.00 | `20260420T144750Z-locomo-mc10-full-context-oracle` | Deterministic mode uses gold labels directly and is only an upper bound. |

## LLM Rows

LLM rows are pending for this public report.

- local `LLM_MODEL` was not configured
- local `LLM_API_KEY` was not configured
- the repository now includes a manual LLM path in `scripts/reproduce_llm_smoke.sh`
- prompt builders live in `src/wiki_memory_bench/systems/answering.py`
- LLM judge prompting lives in `src/wiki_memory_bench/judges/llm_judge.py`

That means no public LLM-answerer or LLM-judge row is being claimed in this report.

## Prompt / Model Settings

Deterministic rows:

- answerer mode: `deterministic`
- judge mode: `deterministic`
- model: `n/a`

Pending LLM rows:

- answerer mode: `llm`
- judge mode: `deterministic` for requested `locomo-mc10` rows
- judge mode: `llm` for requested `longmemeval-s` rows
- model: pending local or workflow-dispatched `LLM_MODEL`
- cache and artifact behavior: see `docs/llm-evaluation.md`

## Failure Analysis

- `locomo-mc10` remains a hard public benchmark slice. All non-oracle deterministic systems in this run are below `40%` accuracy.
- `bm25` was the strongest simple non-oracle baseline on the `locomo-mc10` slice here, outperforming both `vector-rag` and `clipwiki`.
- `clipwiki curated` only slightly improved over `clipwiki full-wiki`, suggesting that current heuristic session selection is not yet a decisive advantage on this public dataset.
- `vector-rag` retrieved fewer tokens than `bm25`, but that efficiency did not translate into higher answer accuracy on this slice.
- `full-context-oracle` reached `100%` accuracy, which highlights how large the gap is between public deployable baselines and a gold-label upper bound.
- On the `longmemeval-s` alpha slice, `bm25` and `clipwiki` were much closer than on `locomo-mc10`, and both achieved strong legacy citation precision.

## Interpretation

What this report does support:

- there is now at least one public dataset story with both RAG and ClipWiki rows
- weak public results are being kept visible instead of hidden
- oracle rows are clearly separated from the main non-oracle table

What this report does not support:

- any claim that `wiki-memory-bench` has finished public benchmarking
- any claim that `clipwiki` is already the best baseline overall
- any claim that these alpha slices are final leaderboard-quality experiments
