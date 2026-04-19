# Acknowledgements

`wiki-memory-bench` is built in conversation with a number of public datasets, open-source memory systems, and infrastructure libraries.

This project reimplements its own benchmark harness and baseline code, but it draws heavily on the design space opened up by the projects below.

## Datasets
### LoCoMo and LoCoMo-MC10
- Original long-conversation memory benchmark from the LoCoMo authors
- Multiple-choice derivative used here through `Percena/locomo-mc10`
- Relevant to:
  - long conversational memory
  - session summaries
  - temporal reasoning
  - multi-session grounding

### LongMemEval-cleaned
- Cleaned release of LongMemEval from `xiaowu0162/longmemeval-cleaned`
- Relevant to:
  - timestamped history
  - evidence session metadata
  - question-type-aware memory evaluation

### MemoryAgentBench
- Helpful as a reference for memory capability framing and evaluation decomposition
- Especially useful for thinking about retrieval, conflict resolution, and evaluation protocol design

## Related Memory Systems and Repositories
### basic-memory
- Demonstrates a pragmatic local Markdown memory system with search and structured editing
- Helpful reference for:
  - local-first memory
  - targeted note edits
  - hybrid retrieval thinking

### llm-wiki-skill
- Strong reference point for wiki-style compiled memory
- Helpful for:
  - source pages
  - wiki organization
  - maintenance workflows
  - health-check style thinking

### agentmemory
- Useful as a reference for retrieval design and benchmark positioning
- Helpful for:
  - hybrid retrieval
  - retrieval instrumentation
  - token-savings-oriented evaluation

## Core Libraries
### LiteLLM
- Unified provider access for optional LLM answerer and judge modes
- Lets the benchmark work across:
  - OpenAI
  - Anthropic
  - Gemini
  - OpenRouter
  - local OpenAI-compatible endpoints

### sentence-transformers
- Used for local embedding-based retrieval in `vector-rag`

### Hugging Face Hub
- Used for dataset downloads and local caching

### Typer, Pydantic, Rich, pytest
- The benchmark CLI, schemas, terminal UX, and test workflow are built on these tools

## Licensing Notes
This repository does not yet include its own finalized project license.

Dataset licenses and usage terms vary. Before public release or redistribution, verify the licenses of:

- `Percena/locomo-mc10`
- `xiaowu0162/longmemeval-cleaned`
- any future datasets or adapters you add

Do not assume that every referenced dataset is suitable for every commercial or redistribution setting.

## Thanks
Thanks to the maintainers and authors of the public datasets and memory-system projects that made this space legible enough to benchmark seriously.
