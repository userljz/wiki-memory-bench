# v0.1 Non-Goals

This document lists what `wiki-memory-bench` will explicitly **not** build in v0.1.

The purpose of this list is to protect focus. A narrow, finished benchmark is more valuable than a broad unfinished platform.

## 1. Not a Generic Memory Benchmark
v0.1 will not try to cover every memory architecture or every agent-memory research question.

It is specifically about:

- Markdown/Wiki-based memory systems
- chat-clip-derived memory inputs
- retrieval plus maintenance behavior

If a feature does not strengthen that thesis, it should be deferred.

## 2. Not a Full Benchmark Aggregator on Day One
v0.1 will not immediately support every public benchmark mentioned in the longer roadmap.

Specifically deferred:

- full `LongMemEval-cleaned` support
- MemoryAgentBench integration
- multimodal LoCoMo tasks
- event summarization benchmarks

The first release only needs:

- `locomo-mc10`
- a tiny synthetic suite

## 3. Not a Hosted Product or Leaderboard Service
v0.1 will not include:

- a web app
- a hosted leaderboard
- cloud orchestration
- remote job scheduling
- multi-user run management

Rich terminal reporting and local run artifacts are enough.

## 4. Not a Full Personal Knowledge Product
`ClipWiki` is a **reference implementation for evaluation**, not a general-purpose personal knowledge manager.

That means v0.1 will not chase:

- polished end-user wiki UX
- browser ingestion pipelines
- sync across devices
- cloud storage
- plugin ecosystems
- note-taking app integrations

## 5. Not a Universal Adapter Layer Yet
v0.1 will define the adapter interface, but it will not fully ship integrations for every external memory system.

Deferred adapters include:

- `basic-memory`
- `agentmemory`
- `llm-wiki-skill`
- `Mem0`
- `Zep`

The benchmark core must be stable before external adapter work expands the surface area.

## 6. Not an LLM-Judge-First System
v0.1 will not depend on a paid LLM judge for the basic benchmark flow.

We may add `llm_judge.py` scaffolding later, but the first usable release should work through:

- deterministic matching
- evidence-aware citation scoring
- deterministic patch validation

This keeps the benchmark cheaper, easier to test, and more reproducible.

## 7. Not Arbitrary Free-Form Wiki Editing
v0.1 will not attempt to score unconstrained natural-language file diffs over arbitrary Markdown stores.

Instead, maintenance evaluation will start with **structured patch operations** over controlled synthetic tasks.

Deferred:

- open-ended git-style diffs
- full Markdown AST rewrite scoring
- free-form multi-file refactors inside the wiki

## 8. Not a Heavy Infrastructure Stack
The first release will not require:

- a vector database service
- a graph database
- a browser runtime
- a message bus
- a daemonized memory server
- multiple Python or Node services

Local files plus local indices are the desired baseline.

## 9. Not a Massive Model-Comparison Matrix
v0.1 will not try to benchmark a large grid of providers, models, prompts, and retrieval settings.

It should support enough configuration to compare systems fairly, but it should not become a sprawling experiment manager.

The focus is:

- benchmark design
- baseline implementations
- reproducible artifacts

## 10. Not a Data-Collection Project
v0.1 will not collect new large-scale human annotation campaigns.

Synthetic tasks should be:

- hand-authored or template-generated
- deterministic
- small enough to review directly

The project should leverage existing public datasets wherever possible.

## 11. Not a License-Risky Code Copying Exercise
v0.1 will not copy large chunks of code from reference repositories just to move faster.

We may adapt ideas, interfaces, or tiny clearly-attributed snippets if necessary, but the default is to implement our own benchmark core.

## 12. Not an Everything-Roadmap README
The project documentation should not pretend that v0.1 already solves the whole memory-benchmark space.

The first release should clearly say:

- what it supports,
- what it measures,
- what it does not support yet,
- what comes next.

Honest scope is part of the quality bar.
