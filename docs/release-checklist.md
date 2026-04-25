# Release Checklist

## Repository Metadata

Before a public `v0.1-alpha` announcement, set or review:

- repository description:
  - `A reproducible CLI benchmark harness for Markdown/Wiki-style LLM agent memory.`
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

Suggested short description for pinned/release surfaces:

```text
A reproducible CLI benchmark harness for Markdown/Wiki-style LLM agent memory.
```

Suggested topics as one comma-separated line:

```text
llm, agents, memory, benchmark, evals, rag, markdown, wiki, long-term-memory, mcp
```

With GitHub CLI, after authenticating:

```bash
gh repo edit userljz/wiki-memory-bench \
  --description "A reproducible CLI benchmark harness for Markdown/Wiki-style LLM agent memory." \
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
