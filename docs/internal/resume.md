# Resume Notes

## One-Line Description

`wiki-memory-bench` is a reproducible benchmark harness for Markdown / Wiki memory systems used by LLM agents.

## Resume Bullets

- Built `wiki-memory-bench`, a benchmark and CLI evaluation harness for long-term agent memory systems, with deterministic baselines, saved artifacts, and reproducible run reporting.
- Designed diagnostic tasks and regression tests for update handling, stale claims, citation precision, forgetting behavior, and release-readiness checks across synthetic and public datasets.
- Added public benchmark reporting for `locomo-mc10` and `longmemeval-s`, keeping weak rows and oracle rows visible instead of overclaiming system quality.

## GitHub Pinned Repo Blurb

Reproducible benchmark for Markdown/Wiki memory systems in LLM agents, with deterministic baselines, public alpha reports, and explicit oracle vs non-oracle evaluation.

## LinkedIn Post Draft

I built `wiki-memory-bench`, a reproducible benchmark harness for Markdown/Wiki-style long-term memory systems in LLM agents.

The v0.1-alpha release focuses on honest engineering evaluation: deterministic baselines, saved artifacts, citation precision, token/latency tracking, and public reports that keep weak rows visible instead of hiding them. It supports synthetic diagnostic tasks, LoCoMo-MC10, LongMemEval slices, BM25, vector RAG, ClipWiki, and explicit full-context oracle upper bounds.

This is not a SOTA claim. It is a release-quality starting point for testing whether memory systems actually remember, update, cite, and forget in reproducible ways.
