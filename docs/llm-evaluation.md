# LLM Evaluation

`wiki-memory-bench` keeps the default test and CI path deterministic and no-key by design.

Optional LLM evaluation exists for a different purpose: calibration. It lets you answer questions with a real LLM while keeping the default benchmark workflow reproducible for normal users who do not have API keys configured.

## Deterministic CI vs Optional LLM Calibration

- Default CI:
  - runs without API keys
  - uses deterministic answerers and deterministic judging by default
  - is intended to stay cheap, reproducible, and safe for public automation

- Optional LLM smoke:
  - is manual only
  - is intended for local calibration or `workflow_dispatch`
  - uses an LLM answerer with a deterministic judge
  - is cost-bounded and small-limit on purpose

The manual script is:

```bash
bash scripts/reproduce_llm_smoke.sh
```

## Required Environment Variables

Minimum manual setup:

```bash
uv sync --group dev --extra llm --extra vector
export WMB_RUN_LLM_INTEGRATION=1
export LLM_MODEL="openai/gpt-4o-mini"
export LLM_API_KEY="your-api-key"
bash scripts/reproduce_llm_smoke.sh
```

Useful optional controls:

```bash
export WMB_LLM_LIMIT=20
export WMB_RUN_LONGMEMEVAL_LLM=1
export LLM_BASE_URL="http://localhost:8000/v1"
```

If your endpoint truly does not require an API key, you must opt in explicitly:

```bash
export WMB_ALLOW_MISSING_LLM_API_KEY=1
```

That safeguard exists to avoid accidentally launching paid requests with incomplete configuration.

## GitHub Secrets

The optional GitHub Actions workflow is:

- `.github/workflows/llm-smoke.yml`

It is `workflow_dispatch` only. It does not run on every push or pull request.

Expected secret / variable setup:

- repository secret: `LLM_API_KEY`
- optional repository secret: `LLM_BASE_URL`
- workflow input `llm_model`, or repository variable `LLM_MODEL`

The workflow passes these values as environment variables without echoing the API key in logs.

## Interpreting LLM Answerer vs LLM Judge Results

The manual LLM smoke workflow uses:

- `answerer = llm`
- `judge = deterministic`

That means:

- the LLM is responsible for producing the answer
- benchmark scoring still uses the deterministic evaluation path

This is useful when you want to understand:

- whether retrieval quality improves when answer extraction becomes stronger
- whether a wiki-style memory system gives an LLM better evidence than a pure lexical baseline

It is not the same as using an LLM judge. An LLM judge introduces an additional model-based correctness layer that can change both cost and interpretation.

## Cost Caveats

The script is intentionally small and cost-bounded:

- it refuses to run unless `WMB_RUN_LLM_INTEGRATION=1`
- it refuses to run without `LLM_MODEL`
- it refuses to run without `LLM_API_KEY` unless you explicitly allow no-key mode
- the default per-row limit is `20`
- it prints an estimated maximum answerer call count before running

Even then:

- provider-side retries can increase real request count
- token prices differ across providers
- cached responses can make repeated runs look cheaper than a cold run

Treat the generated estimated cost as an engineering estimate, not a billing statement.

## Cache Behavior

LLM requests go through `LiteLLMRuntime`, which caches JSON responses on disk using a prompt hash.

Implications:

- repeated runs with identical prompts may reuse cached responses
- prompt artifacts are saved under each run's `artifacts/llm/answerer/`
- the generated LLM smoke report includes prompt artifact paths, token usage, and estimated cost

If you want a cold run:

- change `WMB_HOME`, or
- remove the relevant LLM cache files under `data/cache/llm`

## Outputs

When the script runs successfully, it generates:

- `reports/llm-smoke-results.md`
- `reports/.llm_smoke_results.jsonl`
- `reports/llm-smoke-run-ids.txt`

It also saves full run artifacts under `runs/`.
