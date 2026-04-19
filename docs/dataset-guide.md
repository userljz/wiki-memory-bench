# Dataset Guide

## Purpose
This guide explains how to add or extend datasets in `wiki-memory-bench`.

The benchmark is built around one rule: every dataset should normalize into the same internal case schema, regardless of its original format.

## Dataset Responsibilities
A dataset adapter should:

1. load raw source data
2. normalize records into `EvalCase`
3. preserve timestamps and evidence metadata when available
4. support `limit` and `sample`
5. prepare reproducible local artifacts under `data/prepared/`

## Where Dataset Code Lives
Add new adapters under:

- `src/wiki_memory_bench/datasets/`

Register them with:

- `@register_dataset`

Export them from:

- `src/wiki_memory_bench/datasets/__init__.py`

## Minimal Adapter Shape

```python
@register_dataset
class MyDataset(DatasetAdapter):
    name = "my-dataset"
    description = "Short description."

    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        ...
```

## Normalized Case Requirements
All datasets eventually emit `EvalCase`.

Important fields:

- `example_id`
- `dataset_name`
- `task_type`
- `question`
- `answer`
- `question_id`
- `question_type`
- `history_clips`
- `gold_evidence`
- `metadata`

Optional but strongly encouraged:

- `choices`
- `correct_choice_index`
- `haystack_sessions`
- `haystack_session_ids`
- `haystack_session_summaries`
- `haystack_session_datetimes`

## Choosing `task_type`
Use:

- `TaskType.MULTIPLE_CHOICE` for MC datasets like `locomo-mc10`
- `TaskType.OPEN_QA` for free-form benchmarks like `longmemeval-s`

The evaluator uses this field to decide which scoring path to apply.

## Evidence Preservation
Do not throw away source information just because the first metric does not use it.

Preserve:

- evidence session ids
- evidence turn ids
- timestamps
- source refs

This enables later metrics such as:

- citation coverage
- retrieved-evidence overlap
- stale-claim analysis

## Prepared Dataset Layout
Prepared data is written to:

```text
data/
  prepared/
    <dataset-name>/
      manifest.json
      examples.jsonl
```

This is handled by the shared dataset base layer.

## Split Handling
If a dataset has multiple variants or splits, prefer one of these approaches:

1. separate public aliases, for example:
   - `longmemeval-s`
   - `longmemeval-m`
   - `longmemeval-oracle`
2. a generic entrypoint plus `--split`, for example:
   - `wmb datasets prepare longmemeval --split s`

Both can coexist.

## Sampling and Limits
Support both:

- `--sample`: random subset for fast checks
- `--limit`: final cap on how many examples to use

The benchmark currently uses a fixed seed for deterministic sampling so the same command is reproducible.

## Fixture Strategy for Tests
Use small local fixtures for CI and fast iteration.

Recommended pattern:

1. create a fixture builder under `tests/`
2. write a tiny raw file to a temp directory
3. point the adapter to it through an env override
4. test conversion and CLI prepare/run paths

This is how current dataset tests avoid heavy network dependence.

## Environment Override Pattern
For datasets backed by remote files, support an env override like:

- `WMB_LOCOMO_MC10_SOURCE_FILE`
- `WMB_LONGMEMEVAL_S_SOURCE_FILE`

This makes tests cheap and deterministic.

## Review Checklist
Before merging a dataset adapter, verify:

1. It preserves timestamps if available.
2. It preserves evidence metadata if available.
3. It uses a clear `question_type`.
4. It passes fixture-backed loader tests.
5. `wmb datasets prepare ...` works.

## Common Pitfalls
- Conflating raw source format with normalized case format
- Dropping evidence metadata too early
- Sampling before parsing in a way that breaks determinism
- Hardcoding network downloads into tests
- Forgetting to document split aliases
