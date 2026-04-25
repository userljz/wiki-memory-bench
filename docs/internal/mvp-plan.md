# MVP Implementation Plan

This document defines the implementation order for `wiki-memory-bench` after the planning phase is approved.

The guiding rule is: **ship a working narrow benchmark first, then widen support**.

## Phase 0: Align Repository Baseline
Goal:

- turn the repository from a stub into a clean Python 3.11+ benchmark package

Files to touch first:

- `pyproject.toml`
- `.python-version`
- `README.md`
- `src/wiki_memory_bench/__init__.py`
- `src/wiki_memory_bench/cli.py`

Tasks:

1. Raise the project baseline from Python 3.10 to Python 3.11+.
2. Expose a `wmb` CLI entrypoint with Typer.
3. Keep dependencies minimal and aligned with the chosen baselines.
4. Add a short README that explains what the repo is and how to run the MVP.

Exit criteria:

- `uv run wmb --help` works
- repository metadata matches the planned architecture

## Phase 1: Create Core Schemas and Utilities
Goal:

- establish the normalized contracts before any dataset or system code

Files:

- `src/wiki_memory_bench/schemas.py`
- `src/wiki_memory_bench/utils/paths.py`
- `src/wiki_memory_bench/utils/logging.py`
- `src/wiki_memory_bench/utils/tokens.py`

Tasks:

1. Define Pydantic models for:
   - history clips
   - prepared examples
   - citations
   - system results
   - run manifests
   - patch operations
2. Define stable paths for:
   - raw data
   - prepared data
   - runs
   - synthetic fixtures
3. Add logging helpers and token accounting helpers.

Exit criteria:

- schemas can serialize and deserialize cleanly
- path helpers centralize all benchmark storage decisions

## Phase 2: Build Dataset Registry and Preparation Pipeline
Goal:

- make datasets discoverable and prepareable from the CLI

Files:

- `src/wiki_memory_bench/datasets/base.py`
- `src/wiki_memory_bench/datasets/locomo_mc10.py`
- `src/wiki_memory_bench/datasets/synthetic.py`
- `src/wiki_memory_bench/datasets/longmemeval.py`

Tasks:

1. Create a dataset registry with:
   - `list_datasets()`
   - `prepare_dataset(name, limit, ...)`
   - `load_prepared_dataset(name)`
2. Implement `synthetic-tiny` first.
3. Implement `locomo-mc10` second, backed by normalized examples from `locomo10.json`.
4. Reserve `longmemeval.py` for the next wave, even if only as a documented placeholder initially.
5. Write prepared artifacts:
   - `manifest.json`
   - `examples.jsonl`

Exit criteria:

- `wmb datasets list` works
- `wmb datasets prepare locomo-mc10 --limit 50` works
- synthetic preparation produces deterministic fixtures

## Phase 3: Implement Run Store and Evaluator Skeleton
Goal:

- create the run loop before building all systems

Files:

- `src/wiki_memory_bench/runner/run_store.py`
- `src/wiki_memory_bench/runner/evaluator.py`
- `src/wiki_memory_bench/runner/report.py`

Tasks:

1. Define the run directory layout.
2. Persist:
   - run manifest
   - per-example predictions
   - aggregate metrics
   - system artifacts
3. Add `runs/latest` resolution.
4. Implement a simple sequential evaluator first.

Exit criteria:

- a dummy system can produce a valid run directory
- `wmb report <run_path>` can read the run store contract

## Phase 4: Implement Deterministic Metrics First
Goal:

- make the benchmark usable without an LLM judge

Files:

- `src/wiki_memory_bench/metrics/exact.py`
- `src/wiki_memory_bench/metrics/multiple_choice.py`
- `src/wiki_memory_bench/metrics/citation.py`
- `src/wiki_memory_bench/metrics/cost.py`
- `src/wiki_memory_bench/metrics/latency.py`
- `src/wiki_memory_bench/judges/deterministic.py`

Tasks:

1. Implement normalized exact match for open-answer tasks.
2. Implement multiple-choice accuracy for synthetic tasks.
3. Implement citation precision against gold evidence refs.
4. Implement token and latency aggregation.
5. Implement deterministic patch correctness checks in `judges/deterministic.py`.

Exit criteria:

- synthetic tasks can be scored without external APIs
- LoCoMo runs produce correctness, citation, token, and latency outputs

## Phase 5: Implement the Baseline System Interface
Goal:

- define one adapter contract that all built-in systems share

Files:

- `src/wiki_memory_bench/systems/base.py`

Tasks:

1. Create the `SystemAdapter` base class.
2. Standardize system configuration and result emission.
3. Ensure each system returns:
   - answer
   - citations
   - token usage
   - latency
   - optional patch output

Exit criteria:

- evaluator can run any registered system through one interface

## Phase 6: Ship the Easy Baselines
Goal:

- get simple, local comparison points online quickly

Files:

- `src/wiki_memory_bench/systems/full_context.py`
- `src/wiki_memory_bench/systems/bm25.py`
- `src/wiki_memory_bench/systems/vector_rag.py`

Tasks:

1. Implement `full-context-oracle` as the sanity upper bound baseline.
2. Implement `full-context-heuristic` as the non-oracle full-context comparison point.
3. Implement `bm25` over normalized clip or session text.
4. Implement `vector-rag` using a local embedding model and local vector index.

Exit criteria:

- all three systems can run on `locomo-mc10`
- run artifacts clearly expose retrieved items and citations where applicable

## Phase 7: Add Wiki-Oriented Baselines
Goal:

- benchmark summary-only memory and wiki-structured memory separately

Files:

- `src/wiki_memory_bench/systems/markdown_summary.py`
- `src/wiki_memory_bench/systems/clipwiki.py`
- `src/wiki_memory_bench/clipwiki/compiler.py`
- `src/wiki_memory_bench/clipwiki/markdown_store.py`
- `src/wiki_memory_bench/clipwiki/patch.py`

Tasks:

1. Implement `markdown-summary` as a compact Markdown condensation baseline.
2. Implement `ClipWiki` as the reference wiki-memory system.
3. Keep `ClipWiki` intentionally constrained:
   - local Markdown files
   - source-backed citations
   - structured patch operations
4. Make maintenance tasks flow through `clipwiki.patch`.

Exit criteria:

- `wmb run --dataset locomo-mc10 --system clipwiki --limit 20` works
- synthetic maintenance tasks can produce and score patches

## Phase 8: Finalize the CLI Surface
Goal:

- expose the promised user-facing commands cleanly

Files:

- `src/wiki_memory_bench/cli.py`

Tasks:

1. Add:
   - `wmb datasets list`
   - `wmb datasets prepare ...`
   - `wmb systems list`
   - `wmb run ...`
   - `wmb report ...`
   - `wmb synthetic generate ...`
2. Make Rich output concise and readable.
3. Ensure errors are actionable and typed.

Exit criteria:

- all target CLI commands from the project brief exist
- happy-path commands are demoable end to end

## Phase 9: Add Tests and Fixtures
Goal:

- make the benchmark stable enough to show publicly

Files:

- `tests/...`

Tasks:

1. Add schema and normalization tests.
2. Add dataset preparation tests for:
   - `synthetic-tiny`
   - `locomo-mc10`
3. Add metric tests for:
   - exact
   - citation
   - patch correctness
4. Add smoke tests for at least:
   - `full-context`
   - `bm25`
   - `clipwiki`
5. Keep tests focused and regression-oriented.

Exit criteria:

- `pytest` passes locally
- core flows have fixture-backed regression coverage

## Phase 10: Finish the Open-Source Presentation Layer
Goal:

- make the project strong enough for public release and job applications

Files:

- `README.md`
- example run artifacts or demo snippets

Tasks:

1. Write a strong README with positioning, quickstart, CLI examples, and roadmap.
2. Include one or two reproducible demo commands.
3. Document supported datasets, systems, and current limitations.
4. Add guidance for future external adapters without implementing them yet.

Exit criteria:

- a new reader can understand the benchmark in a few minutes
- the repo demonstrates engineering clarity, not just code volume

## Recommended Order Summary

1. baseline repo and CLI
2. schemas and paths
3. dataset registry
4. run store and evaluator
5. deterministic metrics
6. simple baselines
7. wiki-oriented baselines
8. tests
9. README and demo polish

## Definition of Done for v0.1
v0.1 is done when:

- the CLI commands in the project brief exist,
- `locomo-mc10` and the tiny synthetic suite both run end to end,
- all five built-in systems produce comparable run artifacts,
- deterministic metrics cover correctness, citation, latency, cost, and synthetic patch evaluation,
- the repo is documented and testable enough to share publicly.
