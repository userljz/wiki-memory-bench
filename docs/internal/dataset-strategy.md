# Dataset Strategy

## Objectives
The dataset strategy for v0.1 should optimize for:

- a working benchmark quickly,
- high inspectability,
- grounded citations,
- maintenance-oriented evaluation,
- a clean upgrade path to larger public datasets later.

The benchmark is not trying to win by raw dataset count in v0.1. It should win by **fit to the wiki-memory problem**.

## Principles

1. **Normalize everything into one schema.** Public datasets should be converted into the same prepared example format used by synthetic tasks.
2. **Preserve grounding fields.** Timestamps, evidence IDs, session IDs, and source references should survive normalization.
3. **Use synthetic data to fill public-data gaps.** Public long-memory datasets mostly test QA and retrieval; synthetic tasks should cover patch correctness, stale claims, and update workflows.
4. **Keep MVP local and reproducible.** Prepared datasets must live under local `data/` artifacts and be runnable without external services.
5. **Do not overfit to one benchmark's format.** Public datasets should be inputs to the benchmark, not the architecture itself.

## v0.1 Dataset Portfolio

### 1. `locomo-mc10`
Source of truth:

- `references/locomo/data/locomo10.json`

Project naming note:

- `locomo-mc10` is a **project-local dataset key**.
- In v0.1 it maps directly to the official 10-conversation `locomo10.json` source.
- We are intentionally **not** creating a new public derivative dataset in this phase.

Why it is the right MVP public dataset:

- small enough to inspect manually,
- long, realistic conversations,
- explicit dialog-level evidence references,
- already includes timestamps and conversation structure,
- aligned with the long-memory use case without needing a huge pipeline.

How it should be normalized:

- one prepared example per QA annotation
- the full conversation history stays available as ordered `history_clips`
- `gold_evidence` preserves LoCoMo dialog IDs
- session timestamps are retained in clip metadata
- dataset-level metadata records the original `sample_id`

How `--limit` should work:

- after flattening QA annotations into prepared examples
- not by limiting the number of raw conversations first

How it should be evaluated in v0.1:

- primary: normalized open-answer correctness
- supporting: citation precision against gold dialog IDs
- always: token usage and latency

What is intentionally deferred:

- event summarization
- multimodal generation
- a separate public LoCoMo-derived benchmark release

## 2. Tiny Synthetic Suite
The synthetic suite is required because public datasets do not sufficiently cover wiki maintenance behavior.

### Why synthetic data is necessary
We need tasks that public datasets do not give us directly:

- stale-claim handling
- page update behavior
- patch correctness
- controlled citation placement
- deterministic evaluation of maintenance outcomes

### Design requirements
Synthetic cases should be:

- small and readable,
- deterministic,
- versioned in-repo,
- authored around chat clips rather than abstract triples,
- auditable without an LLM judge.

### Recommended task families

#### `qa_multiple_choice`
- small retrieval-heavy questions over curated clips
- useful for fast smoke tests and deterministic metric coverage

#### `maintenance_patch`
- system must propose a structured wiki update
- gold answer is a canonical patch or resulting page snapshot

#### `stale_claim_resolution`
- system must supersede or mark an outdated claim
- expected output includes both updated content and stale-claim treatment

#### `citation_sensitive_update`
- system must attach or preserve the right source reference when updating a page

### Two synthetic layers

#### `synthetic-tiny`
- hand-authored
- checked into the repository
- used in CI and regression tests

#### generated synthetic cases
- produced by `wmb synthetic generate --cases N`
- useful for experiments and demos
- should reuse deterministic templates, not free-form LLM-only generation

## `LongMemEval-cleaned` as the Next Public Dataset
Source:

- official `longmemeval-cleaned` release

Why it is phase-2 instead of phase-1:

- larger and more expensive to iterate on
- best paired with stronger answer-judging logic
- requires clearer policy around abstention and LLM-judge fallback

What we should preserve when we add it:

- question type taxonomy
- evidence session IDs
- turn-level evidence flags
- abstention cases
- cleaned version metadata

What it gives us later:

- a stronger large-scale public benchmark for open-answer memory QA
- better coverage of temporal reasoning and knowledge updates
- a more benchmark-like evaluation set once the MVP core is stable

## MemoryAgentBench as a Future Integration Layer
MemoryAgentBench should be treated as a later source of **task framing** and **normalized HF metadata**, not as a day-one dependency.

When it becomes useful:

- once `wiki-memory-bench` supports more than one question per context efficiently
- once we add richer update and conflict-resolution task families
- once external-system adapters become a bigger focus

Why it is not in v0.1:

- too broad for the first release
- too much runtime and dataset complexity for the immediate goal

## Normalized Prepared Dataset Contract
All datasets should prepare into the same local structure:

```text
data/
  raw/
    <dataset_name>/
  prepared/
    <dataset_name>/
      manifest.json
      examples.jsonl
```

Each prepared example should minimally include:

- `example_id`
- `dataset_name`
- `task_type`
- `history_clips`
- `question`
- `gold_answer`
- `gold_evidence` (optional)
- `choices` (optional)
- `gold_patch` (optional)
- `metadata`

This is the contract that lets one runner evaluate many system types.

## Evidence and Citation Policy
Evidence fields should be preserved even if a dataset's native metric does not use them directly.

### LoCoMo
- preserve dialog IDs from `evidence`
- map them onto normalized clip identifiers

### LongMemEval-cleaned
- preserve evidence session IDs
- preserve turn-level `has_answer` markers when available

### Synthetic
- create explicit gold source references per claim or answer

This policy is necessary because citation quality is one of the differentiators of `wiki-memory-bench`.

## Data Storage and Versioning

### Raw data
- stored under `data/raw/`
- not committed to git
- downloader or preparer should record provenance in `manifest.json`

### Prepared data
- stored under `data/prepared/`
- can be regenerated deterministically
- tied to a preparation version and parameters

### Synthetic fixtures
- tiny hand-authored fixtures can live in the repository because they are part of the testable benchmark definition

## Recommended Order of Dataset Work

1. Build the normalized dataset schema and manifest format.
2. Implement `synthetic-tiny` first so scoring and maintenance tasks are testable immediately.
3. Implement `locomo-mc10` second so the run loop has a public dataset.
4. Add `LongMemEval-cleaned` after the core metrics and run artifacts are stable.
5. Consider MemoryAgentBench only after the benchmark core proves useful.

## Success Criteria for v0.1 Data
The v0.1 dataset layer is successful if:

- `wmb datasets prepare locomo-mc10 --limit 50` produces deterministic local artifacts,
- the synthetic suite can test patch correctness without manual judging,
- evidence survives normalization,
- future datasets can slot into the same schema without rewriting the runner.
