# Reports

Files in this directory are generated benchmark artifacts.

They are useful for reproducibility, auditability, and debugging, but they are not automatically equivalent to final scientific claims.

## What These Reports Are

- point-in-time snapshots tied to a specific commit, environment, and command set
- generated outputs from scripts such as `scripts/reproduce_v0_1_alpha.sh`
- honest records that should keep weak or poor-performing rows visible
- citation reports now prefer evidence-aware source metrics when `expected_source_ids` are available, and fall back to quote matching only when source ids are unavailable

Generated reports distinguish between:

- `evaluated_source_commit`: the source commit used when the benchmark run itself was executed
- `report_generated_at`: the time the report file was generated
- `source_tree_status_at_generation`: whether the source tree was clean or dirty when the report was generated
- `report_file_commit_note`: a plain-language note explaining that the report file may be committed after the benchmarked source commit

The evaluated source commit and the eventual commit containing the report file
are often different. A committed report cannot honestly contain the hash of the
commit that will only exist after the generated file is added. If the working
tree is dirty, report generation requires `WMB_ALLOW_DIRTY_REPORT=1` and the
report includes a prominent warning plus the dirty tree details.

## What These Reports Are Not

- not a substitute for a full paper-quality experimental protocol
- not proof that one system is generally better than another across all datasets
- not a guarantee that smoke-scale rows are stable research conclusions

In particular, small-limit rows such as `synthetic-mini` are smoke benchmarks. They are useful for sanity checks, not for final leaderboard claims.

## How To Reproduce

Core environment:

```bash
uv sync --group dev
```

If you want rows that depend on optional vector retrieval:

```bash
uv sync --group dev --extra vector
```

Then generate the alpha report:

```bash
./scripts/reproduce_v0_1_alpha.sh
```

The resulting report is written to `reports/v0.1-alpha-results.md`.

For exact post-commit reproducibility, prefer workflow artifacts from the CI or release run that produced the report. The artifact bundle is the clearest record of the evaluated source snapshot, generated markdown, run IDs, and execution environment at the time the report was created.
