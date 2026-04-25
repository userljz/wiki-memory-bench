# Research Notes

## Purpose
These notes summarize the reference repositories and datasets under `references/` and translate them into concrete design guidance for `wiki-memory-bench`.

This project is intentionally narrower than a generic agent-memory benchmark:

- It is **Markdown/Wiki-first**, not memory-system-agnostic.
- It uses **human-curated chat clips** as the canonical memory input format.
- It evaluates **memory maintenance**, not only answer recall.
- It includes a **reference implementation** (`ClipWiki`) rather than only external-system adapters.

The rule for reuse is simple: borrow **concepts, interfaces, and evaluation ideas**, but do **not** import external runtime complexity or copy implementation code unless absolutely necessary.

## Benchmark and Dataset References

### LongMemEval
Relevant files:

- `references/LongMemEval/README.md`
- `references/LongMemEval/src/evaluation/evaluate_qa.py`

What it does:

- Evaluates long-term memory for chat assistants over **timestamped multi-session history**.
- Ships **500 question instances** with question types such as information extraction, multi-session reasoning, knowledge update, temporal reasoning, and abstention.
- Provides both long-history variants and an **oracle retrieval** variant.

Concepts we should reuse:

- **Question-type-aware evaluation** instead of a single undifferentiated score.
- A clean **prediction contract**: system output is a simple record keyed by `question_id`.
- Explicit **evidence annotations** at session or turn level.
- The distinction between:
  - answer correctness,
  - retrieval correctness,
  - abstention handling.

What we should not reuse directly:

- An OpenAI-only evaluation dependency as the default MVP path.
- The full experimental stack around long-context model serving and dense retrievers.
- A benchmark shape centered only on QA accuracy; `wiki-memory-bench` must also cover citation quality, maintenance, stale claims, cost, and latency.

Implication for `wiki-memory-bench`:

- `LongMemEval-cleaned` is a strong **phase-2 public dataset** because it already has timestamps, evidence, and task taxonomy.
- Its evaluation contract strongly informs our future `llm_judge` module, but MVP should avoid making an LLM judge mandatory.

### LoCoMo (`locomo10.json`)
Relevant files:

- `references/locomo/README.MD`
- `references/locomo/data/locomo10.json`

What it does:

- Provides **10 very long conversations** with QA annotations, event summaries, generated observations, and generated session summaries.
- Keeps evidence at the **dialog ID** level, which is valuable for grounded evaluation.
- Reflects more natural long-term conversational memory than synthetic haystack-only benchmarks.

Concepts we should reuse:

- **Human-readable multi-session dialogue** as the base memory source.
- Explicit **evidence references** (`D1:3`, etc.) that can support citation precision.
- Multiple possible retrieval granularities:
  - raw dialogue turns,
  - session summaries,
  - observation summaries.

What we should not reuse directly:

- The whole LoCoMo experimental stack for closed/open models and RAG scripts.
- Event summarization and multimodal generation in v0.1.

Important naming decision for this project:

- MVP will use the CLI dataset key **`locomo-mc10`**.
- For v0.1, that key maps to the official source file `references/locomo/data/locomo10.json`.
- We are **not** introducing a separate derived multiple-choice dataset in this planning phase; the key is a project-local normalized identifier.

Implication for `wiki-memory-bench`:

- LoCoMo is the best first public dataset for MVP because it is small, understandable, evidence-bearing, and easy to inspect during development.
- It should be treated as a **high-signal small benchmark**, not as a final large-scale leaderboard foundation.

### MemoryAgentBench
Relevant files:

- `references/MemoryAgentBench/README.md`
- `references/MemoryAgentBench/utils/eval_data_utils.py`

What it does:

- Benchmarks memory agents under **incremental multi-turn interaction**.
- Frames the space around four capabilities:
  - Accurate Retrieval,
  - Test-Time Learning,
  - Long-Range Understanding,
  - Conflict Resolution.
- Uses an **inject once, query multiple times** philosophy to improve evaluation efficiency.

Concepts we should reuse:

- A capability framing that separates retrieval from updating and conflict handling.
- A normalized dataset view where one context can support **multiple linked questions**.
- HuggingFace-oriented dataset packaging with metadata-driven filtering.

What we should not reuse directly:

- Its broad, multi-benchmark runtime and environment complexity.
- Heavy dependencies around many agent frameworks and external memory systems.
- A benchmark scope wider than the wiki-memory niche.

Implication for `wiki-memory-bench`:

- MemoryAgentBench is a **phase-3 reference** for broadening task families and multi-question-per-context evaluation.
- The most valuable thing to borrow is its **evaluation framing**, not its whole runtime.

## Reference Memory-System Repositories

### `llm-wiki-skill`
Relevant files:

- `references/llm-wiki-skill/README.md`
- `references/llm-wiki-skill/scripts/validate-step1.sh`
- `references/llm-wiki-skill/scripts/source-record-contract.tsv`

What it does:

- Implements a Markdown/wiki workflow inspired by the Karpathy `llm-wiki` idea.
- Separates immutable **raw sources** from generated **wiki pages**.
- Enforces structured ingest with validation, source contracts, confidence labels, and health checks.

Concepts we should reuse:

- The idea that memory is **compiled once and maintained over time**, not regenerated from scratch on every query.
- A fixed wiki information architecture such as:
  - `raw/`
  - `wiki/sources/`
  - `wiki/entities/`
  - `wiki/topics/`
- **Source contracts** and **confidence labels**.
- Mechanical quality checks such as broken links, orphaned pages, and index consistency.

What we should not reuse directly:

- Shell-heavy installer and platform-specific skill logic.
- Optional adapter matrix for web extraction, browsers, and external content pipelines.
- The whole end-user workflow surface area around hooks and interactive ingestion.

Implication for `wiki-memory-bench`:

- This is the closest conceptual inspiration for the `ClipWiki` reference system.
- It strongly supports the idea that `wiki-memory-bench` should evaluate **maintenance quality**, not just retrieval.

### `basic-memory`
Relevant files:

- `references/basic-memory/README.md`
- `references/basic-memory/src/basic_memory/schemas/search.py`
- `references/basic-memory/src/basic_memory/mcp/tools/edit_note.py`

What it does:

- Maintains a local Markdown knowledge base plus local indexing/search infrastructure.
- Supports lexical, vector, and hybrid retrieval.
- Exposes targeted Markdown note editing operations instead of only full rewrites.

Concepts we should reuse:

- A clear search abstraction with **FTS**, **vector**, and **hybrid** modes.
- Deterministic editing primitives such as:
  - `append`
  - `prepend`
  - `find_replace`
  - `replace_section`
- Separation between the **human-readable Markdown store** and the **retrieval/index layer**.

What we should not reuse directly:

- Its full product surface, including cloud routing and multi-backend database support.
- Its licensing and implementation stack as the benchmark core.

Implication for `wiki-memory-bench`:

- `basic-memory` is the best reference for designing **patch-style maintenance tasks** that are constrained and auditable.
- Its editing semantics justify using structured patch operations in MVP instead of arbitrary file diffs.

### `agentmemory`
Relevant files:

- `references/agentmemory/README.md`
- `references/agentmemory/src/state/hybrid-search.ts`

What it does:

- Builds a general memory server around hooks, retrieval, compression, and hybrid search.
- Combines **BM25**, **vector retrieval**, and **graph retrieval** with weighted **RRF-style fusion**.
- Emphasizes observability, retrieval quality, and large runtime coverage across agent clients.

Concepts we should reuse:

- Hybrid retrieval as a meaningful baseline family.
- Weighted fusion and graceful fallback when vector search is unavailable.
- Session-aware diversification and debug visibility for retrieval results.

What we should not reuse directly:

- Its runtime footprint and infrastructure requirements.
- A general-purpose multi-agent memory server as a dependency of the benchmark core.

Implication for `wiki-memory-bench`:

- `agentmemory` validates that a **hybrid or multi-signal baseline** is worth supporting later.
- For MVP, the useful takeaway is retrieval design, not its infrastructure.

## Cross-Cutting Design Conclusions

### What the benchmark core should absorb

1. **Normalized prepared datasets** with timestamps, evidence refs, and stable example IDs.
2. **Simple run contracts**: each system returns answer output, citations, optional maintenance output, and resource stats.
3. **Deterministic first, LLM-judge second**: start with exact/multiple-choice/citation/patch metrics, then add judge-based scoring later.
4. **Maintenance-aware tasks**: stale claim handling and patch correctness belong in the benchmark from day one, at least through synthetic cases.
5. **Reference implementation included**: `ClipWiki` should demonstrate the benchmark's intended problem shape instead of relying only on external adapters.

### What the benchmark core should avoid

1. Becoming a universal benchmark for every memory product shape.
2. Depending on any one runtime such as MCP, iii-engine, shell hooks, or browser tooling.
3. Making long-context serving, closed-model APIs, or web extraction prerequisites for the MVP.
4. Using unconstrained free-form file diffs as the first maintenance target; structured patch operations are easier to score reliably.

## Working MVP Thesis
The strongest MVP is:

- a **small but well-structured benchmark**,
- centered on **chat clips -> local wiki memory -> answer/update tasks**,
- with **reproducible local baselines**,
- explicit **citation and maintenance artifacts**,
- and a clear future path to `LongMemEval-cleaned`, more external adapters, and broader judge-based evaluation.
