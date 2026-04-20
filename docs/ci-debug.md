# CI Debug Notes

## Failing Command

GitHub Actions was failing in the `test` job at:

```bash
uv run pytest -vv
```

The exact failing test was:

```text
tests/test_release_script.py::test_reproduce_script_smoke_executes
```

## Root Cause

`scripts/reproduce_v0_1_alpha.sh` read benchmark artifacts from a hard-coded repository-relative path:

```text
runs/latest/summary.json
runs/latest/manifest.json
runs/latest/predictions.jsonl
```

In CI, `test_reproduce_script_smoke_executes` runs the script with a temporary `WMB_HOME`. The benchmark run artifacts are therefore created under:

```text
$WMB_HOME/runs/latest/
```

The script was still reading from the repository root instead of the configured benchmark home, so CI raised:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'runs/latest/summary.json'
```

## Files Changed

- `scripts/reproduce_v0_1_alpha.sh`
- `docs/ci-debug.md`

## Final Local Command Outputs

```text
uv sync --group dev
Resolved 92 packages in 1ms
Checked 31 packages in 8ms
```

```text
uv run pytest -vv
68 passed, 1 skipped in 3.32s
```

```text
uv run wmb datasets list
Passed. Listed synthetic-mini, synthetic-wiki-memory, locomo-mc10, and LongMemEval variants.
```

```text
uv run wmb systems list
Passed. Listed bm25, clipwiki, vector-rag, full-context-oracle, full-context-heuristic, and basic-memory.
```

```text
uv run wmb run --dataset synthetic-mini --system bm25 --limit 5
Run ID: 20260420T124306Z-synthetic-mini-bm25
Accuracy: 100.00%
Citation precision: 80.00%
```

```text
uv run wmb report runs/latest
Passed. Rendered Run Overview for synthetic-mini / bm25.
```

## GitHub Actions Run URL After Push

Pending push.
