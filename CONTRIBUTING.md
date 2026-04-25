# Contributing

Thanks for considering a contribution to `wiki-memory-bench`.

This project is a benchmark harness, so correctness, reproducibility, and honest reporting matter more than feature volume.

## Development Setup

```bash
uv sync --group dev
uv run pytest
```

Optional extras:

```bash
uv sync --group dev --extra vector
uv sync --group dev --extra llm
```

Do not make optional LLM or vector paths required for default CI.

## Contribution Guidelines

- Keep the default path no-key and deterministic.
- Separate deterministic results, optional LLM calibration, oracle upper bounds, and non-oracle fair baselines.
- Do not claim SOTA or leaderboard significance from small alpha slices.
- Preserve run artifacts and manifests so results are reproducible.
- Add focused regression tests for benchmark behavior changes.
- Avoid committing generated `data/`, `runs/`, `.env*`, credentials, or local caches.

## Adding A Dataset

1. Add a dataset adapter under `src/wiki_memory_bench/datasets/`.
2. Convert records into the normalized `EvalCase` schema.
3. Preserve source metadata, timestamps, evidence IDs, and split information.
4. Add fixture-backed tests and at least one CLI prepare/run path.

See [`docs/dataset-guide.md`](docs/dataset-guide.md).

## Adding A System

1. Add a system adapter under `src/wiki_memory_bench/systems/`.
2. Implement `SystemAdapter.run()`.
3. Record citations, retrieved items, token usage, and end-to-end `latency_ms`.
4. Add tests for correctness, artifacts, and any optional dependency behavior.

See [`docs/adapter-guide.md`](docs/adapter-guide.md).

## LLM And Secret Handling

Real LLM evaluation is manual and opt-in. Use environment variables such as `LLM_API_KEY`; never commit keys or paste them into reports.

Default tests must pass without API keys:

```bash
uv run pytest
```

## Release Hygiene

Before public release work:

- run the default test suite
- verify README commands
- keep weak rows visible
- document provenance and dirty-tree state
- do not publish to PyPI unless explicitly planned

See [`docs/release-checklist.md`](docs/release-checklist.md).
