# Technical Report Outline

## Working Title
`wiki-memory-bench: Evaluating Markdown/Wiki-Based Long-Term Memory Systems for LLM Agents`

## 1. Abstract
- Problem: existing memory benchmarks under-measure wiki-style memory maintenance.
- Contribution: a reproducible benchmark and harness for Markdown/Wiki memory systems.
- Scope: public datasets, synthetic diagnostics, deterministic baselines, optional LLM answerer/judge.
- Headline results: retrieval, answer accuracy, citation quality, maintenance-oriented diagnostics.

## 2. Motivation
- Why generic memory benchmarks are insufficient for wiki-style systems.
- Why human-curated clips matter.
- Why update / stale / forgetting / citation behavior must be measured directly.

## 3. Problem Definition
- Define the target class of systems:
  - Markdown memory stores
  - wiki-like compiled memory
  - source-backed memory pages
- Define benchmark tasks:
  - multiple-choice QA
  - open QA
  - synthetic maintenance diagnostics
- Define assumptions:
  - local-first operation
  - no persistent vector DB required for MVP
  - reproducible CLI-based execution

## 4. Benchmark Design
- Dataset normalization into a shared case schema.
- System adapter abstraction.
- Run artifact design:
  - predictions
  - retrieval artifacts
  - prompt logs
  - wiki artifacts
- Deterministic-first evaluation philosophy.

## 5. Datasets
### 5.1 LoCoMo-MC10
- Source and license
- Question types
- Why it is useful for long conversational memory

### 5.2 LongMemEval-cleaned
- Supported splits:
  - S
  - M
  - Oracle
- Question types / memory abilities
- Evidence and timestamp structure

### 5.3 Synthetic Wiki-Memory Diagnostics
- Why synthetic generation is necessary
- The 10 diagnostic task types
- Seeded deterministic generation
- Export format and intended use

## 6. Baselines
### 6.1 Full-Context
- Purpose and limitations

### 6.2 BM25
- Lexical retrieval design
- Retrieval units for each dataset family

### 6.3 Vector-RAG
- Local sentence-transformers embeddings
- In-memory embedding index
- Deterministic answerer

### 6.4 ClipWiki
- Deterministic compiler
- Wiki page types
- Modes:
  - oracle-curated
  - full-wiki
  - noisy-curated

## 7. Metrics
### 7.1 Core Metrics
- answer accuracy
- category-level / question-type-level accuracy
- latency
- token usage
- estimated cost

### 7.2 Grounding Metrics
- citation precision
- citation coverage
- retrieved token count
- retrieved chunk count

### 7.3 Synthetic Diagnostic Metrics
- update accuracy
- stale claim avoidance
- forgetting compliance
- citation task accuracy
- patch correctness when applicable

## 8. Optional LLM Components
- LiteLLM-based answerer
- LiteLLM-based judge
- caching and artifact logging
- why deterministic mode remains the default

## 9. Experimental Protocol
- Hardware and runtime notes
- Local model configuration
- command lines used for each benchmark
- how to report deterministic vs LLM-assisted runs separately

## 10. Main Experiments
- LoCoMo-MC10 subset runs
- LongMemEval-S runs
- synthetic diagnostic runs

Recommended result tables:
- system vs dataset
- system vs question type
- wiki mode vs retrieval cost
- deterministic vs LLM answerer

## 11. Ablations
- retrieval depth
- answerer mode
- clipwiki mode
- embedding model choice
- curated vs full memory

## 12. Error Analysis
- common retrieval failures
- stale-claim failures
- long-context over-retrieval
- citation failures
- open-QA extraction failures

## 13. Limitations
- current deterministic open-QA answer extraction is weak
- no patch editor / maintenance executor yet
- no external adapter leaderboard yet
- no final license selected for the repository yet

## 14. Future Work
- markdown-summary baseline
- stronger open-QA extraction
- external system adapters
- broader synthetic maintenance evaluation
- leaderboard / release packaging

## 15. Reproducibility Appendix
- exact CLI commands
- environment variables
- prepared dataset layout
- run artifact layout
- prompt log handling
