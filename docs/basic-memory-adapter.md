# Basic Memory Adapter

## Purpose
This document explains the first external memory system adapter in `wiki-memory-bench`: `basic-memory`.

The adapter is intentionally optional:

- default tests do not require `basic-memory`
- local fallback mode works even when the CLI is not installed
- when the CLI is installed, the adapter can run best-effort `sync` and `search-notes`

## Tested Version
The adapter is currently designed and reviewed against the **Basic Memory v0.19.x CLI contract**, based on the reference repository included under `references/basic-memory/`.

Relevant commands:

- `bm --version`
- `basic-memory sync`
- `basic-memory tool search-notes`

Because upstream evolves independently, command output shape may change over time.

## Installation
Recommended upstream install command:

```bash
uv tool install basic-memory
```

Then verify adapter detection:

```bash
uv run wmb systems doctor basic-memory
```

## How the Adapter Works
### Fallback-first design
The adapter always starts by writing **Basic Memory-compatible Markdown notes** into a run-local project directory.

It then behaves as follows:

1. If `basic-memory` or `bm` is available:
   - run `basic-memory sync` (best effort)
   - run `basic-memory tool search-notes` (best effort)
2. If either step fails:
   - fall back to local lexical retrieval over the written notes

This design keeps the adapter:

- optional
- reproducible
- safe for default tests

### What gets written
For each example, the adapter creates session notes in a run-local project:

- Markdown frontmatter
- a `permalink`
- simple `## Observations`
- transcript content

Artifacts are saved under:

- `runs/<run_id>/artifacts/basic-memory/<example_id>/project/`

## Supported Workflow
Current adapter flow:

- `reset`
- `ingest`
- `retrieve`
- `answer`

The answer step reuses the benchmark's common answerer implementations:

- deterministic
- optional LiteLLM-backed answerer

## CLI Commands
Check adapter status:

```bash
uv run wmb systems doctor basic-memory
```

Run on the synthetic diagnostic dataset:

```bash
uv run wmb synthetic generate --cases 100 --out data/synthetic/wiki_memory_100.jsonl
uv run wmb run --dataset synthetic-wiki-memory --system basic-memory --limit 20
uv run wmb report runs/latest
```

## Limitations
Current limitations of the adapter:

1. It does **not** yet talk to the Basic Memory MCP server directly.
2. CLI search integration is **best effort** and falls back to local lexical search if parsing or command execution fails.
3. The adapter currently writes **session-oriented notes**, not richer semantic note graphs.
4. It does not yet use advanced Basic Memory features such as:
   - schema validation
   - semantic vector search
   - cloud routing
   - graph navigation
5. Upstream `basic-memory` currently documents **Python 3.12+**, while this benchmark targets Python 3.11+, so availability depends on the user's environment and installation path.

## Reproducing the Adapter Behavior
### Without Basic Memory installed
This still works and uses local fallback retrieval:

```bash
uv run wmb run --dataset synthetic-wiki-memory --system basic-memory --limit 20
```

### With Basic Memory installed
This uses the same command, but the adapter will try to:

- detect the CLI
- sync the generated notes
- query them with `search-notes`

Use doctor output to confirm what mode is active:

```bash
uv run wmb systems doctor basic-memory
```

## Testing
Default automated coverage includes:

- mocked subprocess tests
- fallback mode tests
- CLI doctor smoke test
- CLI run smoke test

Optional integration tests are skipped unless:

```bash
export WMB_RUN_BASIC_MEMORY_INTEGRATION=1
```

and the Basic Memory CLI is actually installed.
