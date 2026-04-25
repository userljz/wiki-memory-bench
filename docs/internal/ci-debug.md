# CI Debug Notes

## Target Failure

- Workflow: `CI`
- Job: `test`
- Failing commit: `b42e4fe24e5af9f8dc1150abfb65ec24c8c1baeb`
- Failing run URL: `https://github.com/userljz/wiki-memory-bench/actions/runs/24666125016`

Exact failing GitHub Actions command:

```bash
uv run pytest
```

Local verbose reproduction command used during debugging:

```bash
uv run pytest -vv
```

## Failing Test

```text
tests/test_release_script.py::test_reproduce_script_smoke_executes
```

Historical reproduction on an exported `b42e4fe` snapshot:

```text
1 failed, 67 passed, 1 skipped in 1.77s
```

Failure excerpt:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'runs/latest/summary.json'
```

## Root Cause

At `b42e4fe`, `scripts/reproduce_v0_1_alpha.sh` collected run artifacts from a hard-coded repository-relative path:

```text
runs/latest/summary.json
runs/latest/manifest.json
runs/latest/predictions.jsonl
```

The failing smoke test executes the script with a temporary `WMB_HOME`, so the benchmark artifacts are actually written under:

```text
$WMB_HOME/runs/latest/
```

The smoke benchmark itself succeeded, but the script's post-processing step looked in the wrong directory and crashed while reading `summary.json`.

Current `main` already contains the CI fix: the script now resolves the benchmark home from `WMB_HOME` and reads artifacts from `<benchmark_home>/runs/latest/`. Current `main` also includes a follow-up regression-hardening update in `tests/test_release_script.py` that snapshots a temporary repo before checking commit-hash behavior.

## Files Changed

Historical fix and follow-up hardening relevant to this CI issue:

- `scripts/reproduce_v0_1_alpha.sh`
- `tests/test_release_script.py`

This verification update:

- `docs/internal/ci-debug.md`

## Local Command Outputs

```text
uv sync --group dev
Resolved 92 packages in 1ms
Uninstalled 35 packages in 26.66s
```

```text
uv run pytest -vv
74 passed, 1 skipped in 58.83s
```

```text
uv run wmb datasets list
Listed: locomo-mc10, longmemeval, longmemeval-m, longmemeval-oracle, longmemeval-s, synthetic-mini, synthetic-wiki-memory.
```

```text
uv run wmb systems list
Listed: basic-memory, bm25, clipwiki, full-context-heuristic, full-context-oracle, vector-rag.
```

```text
uv run wmb run --dataset synthetic-mini --system bm25 --limit 5
Run ID: 20260421T000043Z-synthetic-mini-bm25
Accuracy: 100.00%
Citation precision: 80.00%
Avg latency: 0.06 ms
```

```text
uv run wmb report runs/latest
Rendered Run Overview for synthetic-mini / bm25 with 5 examples and 100.00% accuracy.
```

## GitHub Actions Run URL After Push

- Verification push run URL: `https://github.com/userljz/wiki-memory-bench/actions/runs/24696859289`
