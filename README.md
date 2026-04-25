# Wiki-Memory-Bench

[![CI](https://github.com/userljz/wiki-memory-bench/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/userljz/wiki-memory-bench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

**A reproducible CLI benchmark harness for Markdown/Wiki-style LLM agent memory.**

`wiki-memory-bench` helps engineers test whether agent memory systems can retrieve, update, cite, forget, and aggregate long-term information using reproducible local runs and saved artifacts.

Use it if you are building or evaluating Markdown-first memory, wiki-style memory, RAG memory adapters, or long-term agent memory baselines. It is **not** a hosted leaderboard, a SOTA claim, a note-taking product, or a generic benchmark for every memory architecture.

## Install And Run

Core path, no API key:

```bash
uv sync
uv run wmb datasets list
uv run wmb systems list
uv run wmb run --dataset synthetic-mini --system bm25 --limit 5
uv run wmb report runs/latest
```

Expected output shape:

```text
Run Complete
Accuracy: 100.00%
Citation precision: 80.00%
Errors: 0 (0.00%)
```

By default, `wmb run` is fail-fast: a system, evaluator, or judge exception stops the run immediately. Use `--continue-on-error` for batch diagnostics; failed examples are written to `predictions.jsonl`, tracebacks are saved under `artifacts/errors/`, and `summary.json` records `error_count` and `error_rate`.

## 5-Minute Quickstart

Generate a deterministic wiki-memory diagnostic dataset and run a wiki-style baseline:

```bash
uv run wmb synthetic generate --cases 100 --seed 42 --out data/synthetic/wiki_memory_100.jsonl
uv run wmb run --dataset synthetic-wiki-memory --system clipwiki --mode full-wiki --limit 20
uv run wmb report runs/latest
```

Expected output shape:

```text
Run Complete
Dataset: synthetic-wiki-memory
System: clipwiki
Accuracy: ...
Citation source F1: ...
Avg latency: ...
```

Run IDs, predictions, summaries, wiki artifacts, prompt artifacts, and error artifacts are saved under `runs/`.

## What Gets Measured

- Answer accuracy and question-type accuracy.
- Evidence-aware citation source precision, recall, and F1.
- Stale citation rate and unsupported answer rate.
- Token usage, estimated cost, latency, retrieved chunks, and retrieved tokens.
- Wiki size metrics for systems that compile Markdown/Wiki artifacts.
- Optional LLM answerer or judge cost and prompt artifacts.

## Result Types

`wiki-memory-bench` keeps these result categories separate:

| Category | Meaning | Default CI? |
| --- | --- | --- |
| Deterministic no-key results | Local baselines and deterministic scoring. Best for reproducible regression checks. | Yes |
| Optional LLM calibration | Real LLM answerer or judge runs for calibration. Provider-dependent and credential-gated. | No |
| Non-oracle fair baselines | Rows that do not use gold labels during retrieval or answering. | Yes |
| Oracle upper bounds | Rows that use gold labels, such as `full-context-oracle` or `clipwiki --mode oracle-curated`. Useful only as upper bounds. | No |

Do not mix optional LLM calibration or oracle upper bounds into a fair non-oracle leaderboard.

## v0.1-alpha Results

The deterministic alpha snapshot is intentionally small and conservative. Full provenance, commands, run IDs, weak rows, and failure analysis are in [`reports/v0.1-alpha-results.md`](reports/v0.1-alpha-results.md).

| Slice | Systems | Notes |
| --- | --- | --- |
| `synthetic-mini` | `bm25` | Fast smoke sanity check. |
| `synthetic-wiki-memory` | `bm25`, `clipwiki` | Deterministic maintenance diagnostics. |
| `locomo-mc10` | `bm25`, `vector-rag`, `clipwiki` | Weak public alpha rows remain visible. |

Related reports:

- Deterministic alpha report: [`reports/v0.1-alpha-results.md`](reports/v0.1-alpha-results.md)
- Broader public slice: [`reports/public-benchmark-alpha.md`](reports/public-benchmark-alpha.md)
- Optional LLM smoke calibration: [`reports/llm-smoke-results.md`](reports/llm-smoke-results.md)

No result in this release claims that ClipWiki or any other system is SOTA.

## Optional Paths

Vector retrieval:

```bash
uv sync --extra vector
uv run wmb datasets prepare locomo-mc10 --limit 20
uv run wmb run --dataset locomo-mc10 --system vector-rag --limit 20
```

LLM answerer or judge via LiteLLM:

```bash
uv sync --extra llm
export LLM_MODEL="openrouter/tencent/hy3-preview:free"
export LLM_API_KEY="your-openrouter-api-key"
uv run wmb run --dataset locomo-mc10 --system clipwiki --answerer llm --judge deterministic --limit 2
```

Manual LLM smoke:

```bash
uv sync --group dev --extra llm --extra vector
export WMB_RUN_LLM_INTEGRATION=1
export WMB_LLM_LIMIT=20
export LLM_MODEL="openrouter/tencent/hy3-preview:free"
export LLM_API_KEY="your-openrouter-api-key"
bash scripts/reproduce_llm_smoke.sh
```

See [`docs/llm-evaluation.md`](docs/llm-evaluation.md) for cost, cache, and artifact details.

## Supported Datasets And Systems

Datasets:

- `synthetic-mini`
- `synthetic-wiki-memory`
- `locomo-mc10`
- `longmemeval-s`, `longmemeval-m`, `longmemeval-oracle`

Systems:

- `bm25`
- `vector-rag`
- `clipwiki`
- `full-context-heuristic`
- `full-context-oracle`
- `basic-memory` experimental adapter

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/adapter-guide.md`](docs/adapter-guide.md)
- [`docs/dataset-guide.md`](docs/dataset-guide.md)
- [`docs/llm-evaluation.md`](docs/llm-evaluation.md)
- [`docs/synthetic-wiki-memory.md`](docs/synthetic-wiki-memory.md)
- [`docs/release-checklist.md`](docs/release-checklist.md)

Internal planning and release notes live under [`docs/internal/`](docs/internal/).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Contributions should preserve the default no-key CI path and keep oracle, LLM, and deterministic results clearly separated.

## License

MIT License. See [`LICENSE`](LICENSE).
