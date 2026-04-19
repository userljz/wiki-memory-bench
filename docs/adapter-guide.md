# Adapter Guide

## Purpose
This guide explains how to add a new memory system adapter to `wiki-memory-bench`.

The goal is to make adapters easy to write, easy to review, and easy to compare.

## Adapter Contract
Every system adapter lives under `src/wiki_memory_bench/systems/` and should:

1. accept a normalized `PreparedExample`
2. retrieve or compile the relevant memory representation
3. answer the task
4. return a `SystemResult`

The base interface is `SystemAdapter` in `src/wiki_memory_bench/systems/base.py`.

## Minimal Implementation

```python
@register_system
class MyMemorySystem(SystemAdapter):
    name = "my-memory-system"
    description = "Short human-readable description."

    def prepare_run(self, run_dir: Path, dataset_name: str) -> None:
        ...

    def run(self, example: PreparedExample) -> SystemResult:
        ...

    def finalize_run(self) -> None:
        ...
```

## Required Return Shape
Adapters should return a `SystemResult` with as many of these fields as possible:

- `answer_text`
- `selected_choice_id` / `selected_choice_index` / `selected_choice_text` for MC tasks
- `citations`
- `retrieved_items`
- `token_usage`
- `latency_ms`
- `metadata`

Optional but useful:

- `wiki_size_pages`
- `wiki_size_tokens`
- `citation_precision` if the adapter can compute something stronger than the default heuristic

## Lifecycle Hooks
### `prepare_run()`
Use this for run-level setup:

- create adapter-specific artifact directories
- initialize caches
- configure prompt log locations

### `run()`
This is where per-example work happens:

- build or access memory
- retrieve evidence
- answer the question
- populate `SystemResult`

### `finalize_run()`
Use this for teardown:

- flush in-memory logs
- close resources
- write summary files if needed

## Retrieval Artifacts
If the adapter retrieves text or wiki pages, populate `retrieved_items` with:

- `clip_id`
- `rank`
- `score`
- `text`
- `retrieved_tokens`

This is what enables:

- retrieved token statistics
- prompt debugging
- future citation coverage metrics

## Answerer Modes
Current adapters can support:

- `deterministic`
- `llm`

If your adapter supports `llm`, route it through the shared LiteLLM runtime and save artifacts under:

- `runs/<run_id>/artifacts/llm/answerer/`

Do not make `llm` the default mode.

## Judge Interaction
The adapter itself should not decide final correctness. It should emit predictions clearly enough that the evaluator can score them with:

- deterministic metrics
- optional LLM judge

Keep scoring logic out of the adapter when possible.

## Artifact Layout
If your adapter emits custom artifacts, store them under:

- `runs/<run_id>/artifacts/<adapter-name>/...`

For example, `clipwiki` uses:

- `runs/<run_id>/artifacts/wiki/<example-id>/`

External adapters should follow the same principle. For example, the Basic Memory adapter writes its run-local project under:

- `runs/<run_id>/artifacts/basic-memory/<example-id>/project/`

## System Doctor
Optional external adapters should provide a simple doctor path when setup can fail for environment reasons.

Current example:

```bash
uv run wmb systems doctor basic-memory
```

This is especially useful when:

- the adapter depends on an external CLI
- installation may vary by Python version
- the adapter can run in both enhanced and fallback modes

## Testing Checklist
At minimum, add:

1. a unit test for the adapter's core behavior
2. a smoke test on a small dataset fixture
3. a CLI test if the adapter introduces a new flag or mode

Good adapter tests check:

- retrieval works
- citations are emitted
- artifacts are created
- deterministic mode remains local and reproducible

## Common Pitfalls
- Returning answers without citations when the adapter clearly retrieved evidence
- Putting benchmark scoring logic inside the adapter
- Making external services mandatory for basic runs
- Forgetting to write adapter artifacts into the run directory
- Returning provider-specific objects instead of normalized schema models

## Recommended Review Questions
Before merging a new adapter, ask:

1. Can it run without hidden external setup?
2. Does it preserve enough retrieval detail for debugging?
3. Are its outputs normalized and comparable to other systems?
4. Does it have at least one fixture-backed smoke test?
