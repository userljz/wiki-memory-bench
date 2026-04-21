# Reports

Files in this directory are generated benchmark artifacts.

They are useful for reproducibility, auditability, and debugging, but they are not automatically equivalent to final scientific claims.

## What These Reports Are

- point-in-time snapshots tied to a specific commit, environment, and command set
- generated outputs from scripts such as `scripts/reproduce_v0_1_alpha.sh`
- honest records that should keep weak or poor-performing rows visible

Generated reports distinguish between:

- `evaluated_source_commit`: the source commit used when the benchmark run itself was executed
- `report_commit`: the later commit that may add or update the generated markdown file in git history

Those two values are often different. A committed report cannot honestly contain the hash of the commit that will only exist after the generated file is added.

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
