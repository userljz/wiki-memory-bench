# Release Checklist

## Repository Metadata

Before a public `v0.1-alpha` announcement, set or review:

- repository description:
  - `Benchmark Markdown/Wiki memory systems for LLM agents.`
- pinned README links
- license visibility
- issue / discussion settings

Suggested GitHub topics:

- `llm`
- `agents`
- `memory`
- `benchmark`
- `evals`
- `rag`
- `markdown`
- `wiki`
- `long-term-memory`
- `mcp`

With GitHub CLI, after authenticating:

```bash
gh repo edit userljz/wiki-memory-bench \
  --description "Benchmark Markdown/Wiki memory systems for LLM agents." \
  --add-topic llm \
  --add-topic agents \
  --add-topic memory \
  --add-topic benchmark \
  --add-topic evals \
  --add-topic rag \
  --add-topic markdown \
  --add-topic wiki \
  --add-topic long-term-memory \
  --add-topic mcp
```

## Release Notes

- link the reproducible alpha report
- state clearly that this is `v0.1-alpha`
- keep weak rows and skipped rows visible
- do not claim `clipwiki` beats `vector-rag` unless the report actually shows it
- do not publish to PyPI for `v0.1.0-alpha`
