#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${WMB_REPORT_DIR:-$ROOT_DIR/reports}"
RESULTS_JSONL="${WMB_LLM_RESULTS_JSONL:-$REPORT_DIR/.llm_smoke_results.jsonl}"
RUN_IDS_FILE="${WMB_LLM_RUN_IDS_FILE:-$REPORT_DIR/llm-smoke-run-ids.txt}"
REPORT_FILE="${WMB_LLM_REPORT_FILE:-$REPORT_DIR/llm-smoke-results.md}"
LIMIT="${WMB_LLM_LIMIT:-20}"
RUN_LLM_INTEGRATION="${WMB_RUN_LLM_INTEGRATION:-0}"
RUN_LONGMEMEVAL_LLM="${WMB_RUN_LONGMEMEVAL_LLM:-0}"
ALLOW_MISSING_LLM_API_KEY="${WMB_ALLOW_MISSING_LLM_API_KEY:-0}"

if [[ "$RUN_LLM_INTEGRATION" != "1" ]]; then
  echo "Refusing to run LLM smoke evaluation without WMB_RUN_LLM_INTEGRATION=1." >&2
  exit 1
fi

if [[ -z "${LLM_MODEL:-}" ]]; then
  echo "LLM_MODEL is required for LLM smoke evaluation." >&2
  exit 1
fi

if [[ -z "${LLM_API_KEY:-}" && "$ALLOW_MISSING_LLM_API_KEY" != "1" ]]; then
  echo "LLM_API_KEY is required unless you explicitly set WMB_ALLOW_MISSING_LLM_API_KEY=1." >&2
  exit 1
fi

if ! uv run python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('litellm') else 1)" >/dev/null 2>&1; then
  echo "LiteLLM is not installed. Run \`uv sync --extra llm\` before using this script." >&2
  exit 1
fi

if uv run python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('sentence_transformers') else 1)" >/dev/null 2>&1; then
  VECTOR_DEPENDENCY_INSTALLED="true"
else
  VECTOR_DEPENDENCY_INSTALLED="false"
fi

TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
PYTHON_VERSION="$(uv run python --version 2>&1)"
UV_VERSION="$(uv --version 2>/dev/null || echo "uv unavailable")"
PACKAGE_VERSION="$(uv run python -c 'import wiki_memory_bench; print(wiki_memory_bench.__version__)')"

row_count=4
if [[ "$VECTOR_DEPENDENCY_INSTALLED" == "true" ]]; then
  row_count=$((row_count + 1))
fi
if [[ "$RUN_LONGMEMEVAL_LLM" == "1" ]]; then
  row_count=$((row_count + 2))
fi
estimated_calls=$((row_count * LIMIT))

echo "== LLM Smoke Configuration =="
echo "UTC Timestamp: $TIMESTAMP_UTC"
echo "LLM_MODEL: ${LLM_MODEL}"
echo "Python: $PYTHON_VERSION"
echo "uv: $UV_VERSION"
echo "Package version: $PACKAGE_VERSION"
echo "Vector dependency installed: $VECTOR_DEPENDENCY_INSTALLED"
echo "LongMemEval enabled: $RUN_LONGMEMEVAL_LLM"
echo "Limit per row: $LIMIT"
echo "Estimated max LLM answerer calls: $estimated_calls"
echo "Judge mode: deterministic (no extra LLM judge calls)"

mkdir -p "$REPORT_DIR"
: > "$RESULTS_JSONL"
: > "$RUN_IDS_FILE"

COMMANDS_RUN=()
FAILURES=0

run_case() {
  local dataset="$1"
  local system="$2"
  local notes="$3"
  local limitations="$4"
  shift 4

  local cmd=(
    "uv" "run" "wmb" "run"
    "--dataset" "$dataset"
    "--system" "$system"
    "--answerer" "llm"
    "--judge" "deterministic"
    "--limit" "$LIMIT"
  )
  if [[ "$#" -gt 0 ]]; then
    cmd+=("$@")
  fi
  local command_string="${cmd[*]}"
  local log_file
  log_file="$(mktemp)"

  echo
  echo "== Running: $command_string =="
  COMMANDS_RUN+=("$command_string")

  set +e
  "${cmd[@]}" >"$log_file" 2>&1
  local exit_code=$?
  set -e

  cat "$log_file"

  if [[ $exit_code -ne 0 ]]; then
    FAILURES=1
    RESULTS_JSONL="$RESULTS_JSONL" \
    DATASET="$dataset" \
    SYSTEM="$system" \
    LIMIT="$LIMIT" \
    COMMAND_STRING="$command_string" \
    NOTES="$notes" \
    LIMITATIONS="$limitations" \
    VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
    LOG_FILE="$log_file" \
    uv run python - <<'PY'
import json
import os
from pathlib import Path

log_file = Path(os.environ["LOG_FILE"])
log_preview = log_file.read_text(encoding="utf-8")[-4000:]
system = os.environ["SYSTEM"]

record = {
    "status": "failed",
    "dataset": os.environ["DATASET"],
    "system": system,
    "mode": "default",
    "answerer_mode": "llm",
    "judge_mode": "deterministic",
    "model": os.environ.get("LLM_MODEL", ""),
    "limit": int(os.environ["LIMIT"]),
    "accuracy": None,
    "citation_precision": None,
    "avg_latency_ms": None,
    "avg_retrieved_tokens": None,
    "avg_total_tokens": None,
    "total_tokens": None,
    "avg_estimated_cost_usd": None,
    "total_estimated_cost_usd": None,
    "prompt_artifact_path": None,
    "artifact_count": 0,
    "dependency_mode": "vector-extra-installed" if (system == "vector-rag" and os.environ["VECTOR_DEPENDENCY_INSTALLED"] == "true") else ("vector-extra-missing" if system == "vector-rag" else "llm-extra-installed"),
    "command": os.environ["COMMAND_STRING"],
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
    "failure_log_excerpt": log_preview,
}

results_path = Path(os.environ["RESULTS_JSONL"])
with results_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
PY

    if [[ "$system" == "vector-rag" ]]; then
      mkdir -p "$ROOT_DIR/docs"
      cat > "$ROOT_DIR/docs/vector-rag-notes.md" <<EOF
# Vector RAG Notes

The optional LLM smoke row for \`vector-rag\` failed during execution.

- timestamp: \`$TIMESTAMP_UTC\`
- model: \`${LLM_MODEL}\`
- command: \`$command_string\`

Last log excerpt:

\`\`\`text
$(tail -n 80 "$log_file")
\`\`\`
EOF
    fi

    rm -f "$log_file"
    return
  fi

  RESULTS_JSONL="$RESULTS_JSONL" \
  RUN_IDS_FILE="$RUN_IDS_FILE" \
  COMMAND_STRING="$command_string" \
  NOTES="$notes" \
  LIMITATIONS="$limitations" \
  VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
  uv run python - <<'PY'
import json
import os
from pathlib import Path

benchmark_home = Path(os.environ.get("WMB_HOME", ".")).expanduser().resolve()
latest_run_dir = benchmark_home / "runs" / "latest"
summary = json.loads((latest_run_dir / "summary.json").read_text(encoding="utf-8"))
manifest = json.loads((latest_run_dir / "manifest.json").read_text(encoding="utf-8"))
predictions = [
    json.loads(line)
    for line in (latest_run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

artifact_paths = sorted(
    {
        str(result.get("metadata", {}).get("llm_artifact_path"))
        for result in predictions
        if result.get("metadata", {}).get("llm_artifact_path")
    }
)

model_name = os.environ.get("LLM_MODEL", "")
if artifact_paths:
    first_artifact = Path(artifact_paths[0])
    if first_artifact.exists():
        payload = json.loads(first_artifact.read_text(encoding="utf-8"))
        model_name = str(payload.get("model", model_name))

judge_mode = "deterministic"
if predictions:
    judge_mode = str(predictions[0].get("metadata", {}).get("judge_mode", "deterministic"))

answerer_mode = "llm"
if predictions:
    answerer_mode = str(predictions[0].get("metadata", {}).get("answerer_mode", "llm"))

record = {
    "status": "ok",
    "dataset": summary["dataset_name"],
    "system": summary["system_name"],
    "mode": str(predictions[0].get("metadata", {}).get("clipwiki_mode", "default")) if predictions else "default",
    "answerer_mode": answerer_mode,
    "judge_mode": judge_mode,
    "model": model_name,
    "limit": manifest.get("limit"),
    "accuracy": summary.get("accuracy"),
    "citation_precision": summary.get("citation_precision"),
    "avg_latency_ms": summary.get("avg_latency_ms"),
    "avg_retrieved_tokens": summary.get("avg_retrieved_tokens"),
    "avg_total_tokens": summary.get("avg_total_tokens"),
    "total_tokens": summary.get("total_tokens"),
    "avg_estimated_cost_usd": summary.get("avg_estimated_cost_usd"),
    "total_estimated_cost_usd": summary.get("total_estimated_cost_usd"),
    "prompt_artifact_path": artifact_paths[0] if artifact_paths else None,
    "artifact_count": len(artifact_paths),
    "dependency_mode": "vector-extra-installed" if (summary["system_name"] == "vector-rag" and os.environ["VECTOR_DEPENDENCY_INSTALLED"] == "true") else ("vector-extra-missing" if summary["system_name"] == "vector-rag" else "llm-extra-installed"),
    "command": os.environ["COMMAND_STRING"],
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
    "run_id": manifest["run_id"],
    "run_dir": manifest["run_dir"],
}

results_path = Path(os.environ["RESULTS_JSONL"])
with results_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")

run_ids_path = Path(os.environ["RUN_IDS_FILE"])
with run_ids_path.open("a", encoding="utf-8") as handle:
    handle.write(f"{record['run_id']}\t{record['dataset']}\t{record['system']}\n")
PY

  rm -f "$log_file"
}

append_skipped_case() {
  local dataset="$1"
  local system="$2"
  local notes="$3"
  local limitations="$4"

  local command_string="uv run wmb run --dataset $dataset --system $system --answerer llm --judge deterministic --limit $LIMIT"
  COMMANDS_RUN+=("$command_string")

  RESULTS_JSONL="$RESULTS_JSONL" \
  DATASET="$dataset" \
  SYSTEM="$system" \
  LIMIT="$LIMIT" \
  COMMAND_STRING="$command_string" \
  NOTES="$notes" \
  LIMITATIONS="$limitations" \
  uv run python - <<'PY'
import json
import os
from pathlib import Path

record = {
    "status": "skipped",
    "dataset": os.environ["DATASET"],
    "system": os.environ["SYSTEM"],
    "mode": "default",
    "answerer_mode": "llm",
    "judge_mode": "deterministic",
    "model": os.environ.get("LLM_MODEL", ""),
    "limit": int(os.environ["LIMIT"]),
    "accuracy": None,
    "citation_precision": None,
    "avg_latency_ms": None,
    "avg_retrieved_tokens": None,
    "avg_total_tokens": None,
    "total_tokens": None,
    "avg_estimated_cost_usd": None,
    "total_estimated_cost_usd": None,
    "prompt_artifact_path": None,
    "artifact_count": 0,
    "dependency_mode": "vector-extra-missing" if os.environ["SYSTEM"] == "vector-rag" else "llm-extra-installed",
    "command": os.environ["COMMAND_STRING"],
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
}

results_path = Path(os.environ["RESULTS_JSONL"])
with results_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
PY
}

run_case \
  "synthetic-wiki-memory" \
  "bm25" \
  "LLM answerer calibration on the deterministic synthetic wiki-memory diagnostic set." \
  "Small-limit alpha row; useful for calibration, not a scientific leaderboard result."

run_case \
  "synthetic-wiki-memory" \
  "clipwiki" \
  "LLM answerer calibration on the wiki-style deterministic baseline." \
  "Small-limit alpha row; prompt quality and retrieval quality are both in play."

run_case \
  "locomo-mc10" \
  "bm25" \
  "LLM answerer over lexical retrieval on LoCoMo-MC10." \
  "Unauthenticated Hugging Face access may reduce reliability or speed when datasets are not cached."

if [[ "$VECTOR_DEPENDENCY_INSTALLED" == "true" ]]; then
  run_case \
    "locomo-mc10" \
    "vector-rag" \
    "LLM answerer over local embedding retrieval on LoCoMo-MC10." \
    "This row depends on local sentence-transformers model availability and download reliability."
else
  append_skipped_case \
    "locomo-mc10" \
    "vector-rag" \
    "Skipped because vector dependencies are not installed." \
    "Install the optional vector stack to evaluate vector-rag in LLM smoke mode."
fi

run_case \
  "locomo-mc10" \
  "clipwiki" \
  "LLM answerer over deterministic full-wiki retrieval on LoCoMo-MC10." \
  "Wiki compilation quality and prompt following both affect this row." \
  "--mode" "full-wiki"

if [[ "$RUN_LONGMEMEVAL_LLM" == "1" ]]; then
  run_case \
    "longmemeval-s" \
    "bm25" \
    "Optional LLM answerer calibration on LongMemEval-cleaned S split with lexical retrieval." \
    "Open-QA row with external dataset access; run only when explicitly enabled."

  run_case \
    "longmemeval-s" \
    "clipwiki" \
    "Optional LLM answerer calibration on LongMemEval-cleaned S split with wiki retrieval." \
    "Open-QA row with external dataset access; run only when explicitly enabled." \
    "--mode" "full-wiki"
fi

COMMANDS_JSON="$(printf '%s\n' "${COMMANDS_RUN[@]}" | uv run python -c 'import json,sys; print(json.dumps(sys.stdin.read().splitlines()))')"
COMMANDS_JSON="$COMMANDS_JSON" \
RESULTS_JSONL="$RESULTS_JSONL" \
RUN_IDS_FILE="$RUN_IDS_FILE" \
REPORT_FILE="$REPORT_FILE" \
TIMESTAMP_UTC="$TIMESTAMP_UTC" \
VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
LIMIT="$LIMIT" \
ESTIMATED_CALLS="$estimated_calls" \
RUN_LONGMEMEVAL_LLM="$RUN_LONGMEMEVAL_LLM" \
uv run python - <<'PY'
import json
import os
from pathlib import Path

results = [
    json.loads(line)
    for line in Path(os.environ["RESULTS_JSONL"]).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
commands = json.loads(os.environ["COMMANDS_JSON"])
run_ids_text = Path(os.environ["RUN_IDS_FILE"]).read_text(encoding="utf-8").strip()
report_path = Path(os.environ["REPORT_FILE"])


def fmt_pct(value):
    if value is None:
        return "skipped"
    return f"{value * 100:.2f}%"


def fmt_num(value):
    if value is None:
        return "skipped"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


lines: list[str] = []
lines.append("# LLM Smoke Results")
lines.append("")
lines.append("This report is generated by `scripts/reproduce_llm_smoke.sh` for optional, manual LLM calibration runs.")
lines.append("")
lines.append("## Environment")
lines.append("")
lines.append(f"- timestamp (UTC): `{os.environ['TIMESTAMP_UTC']}`")
lines.append(f"- model: `{os.environ.get('LLM_MODEL', '')}`")
lines.append(f"- vector dependency installed: `{os.environ['VECTOR_DEPENDENCY_INSTALLED']}`")
lines.append(f"- limit per row: `{os.environ['LIMIT']}`")
lines.append(f"- estimated max answerer calls before run: `{os.environ['ESTIMATED_CALLS']}`")
lines.append(f"- optional LongMemEval rows enabled: `{os.environ['RUN_LONGMEMEVAL_LLM']}`")
lines.append("")
lines.append("## Commands Run")
lines.append("")
for command in commands:
    lines.append(f"- `{command}`")
lines.append("")
lines.append("## Result Table")
lines.append("")
lines.append("| Dataset | System | Mode | Answerer Mode | Judge Mode | Model | Status | Accuracy | Citation Precision | Avg Tokens | Total Tokens | Avg Cost | Total Cost | Prompt Artifact Path |")
lines.append("| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
for record in results:
    lines.append(
        "| {dataset} | {system} | {mode} | {answerer_mode} | {judge_mode} | {model} | {status} | {accuracy} | {citation_precision} | {avg_total_tokens} | {total_tokens} | {avg_cost} | {total_cost} | {artifact_path} |".format(
            dataset=record["dataset"],
            system=record["system"],
            mode=record["mode"],
            answerer_mode=record["answerer_mode"],
            judge_mode=record["judge_mode"],
            model=record["model"] or os.environ.get("LLM_MODEL", ""),
            status=record["status"],
            accuracy=fmt_pct(record.get("accuracy")),
            citation_precision=fmt_pct(record.get("citation_precision")),
            avg_total_tokens=fmt_num(record.get("avg_total_tokens")),
            total_tokens=fmt_num(record.get("total_tokens")),
            avg_cost=fmt_num(record.get("avg_estimated_cost_usd")),
            total_cost=fmt_num(record.get("total_estimated_cost_usd")),
            artifact_path=record.get("prompt_artifact_path") or "n/a",
        )
    )
lines.append("")
lines.append("## Run IDs")
lines.append("")
if run_ids_text:
    lines.append("```text")
    lines.extend(run_ids_text.splitlines())
    lines.append("```")
else:
    lines.append("No successful run IDs were recorded.")
lines.append("")
lines.append("## Known Limitations")
lines.append("")
lines.append("- These are manual, cost-bounded smoke evaluations. They are not default CI and they are not final leaderboard claims.")
lines.append("- Results depend on provider behavior, caching, model choice, prompt stability, and any local OpenAI-compatible endpoint configuration.")
lines.append("- `deterministic judge` means answer quality is being calibrated with LLM answerers while keeping correctness scoring deterministic.")
lines.append("- Prompt artifacts are saved under each run's `artifacts/llm/answerer/` directory so prompt/response details can be audited later.")
lines.append("")
lines.append("## Failure Analysis")
lines.append("")
failed = [record for record in results if record["status"] == "failed"]
skipped = [record for record in results if record["status"] == "skipped"]
if not failed and not skipped:
    lines.append("- All configured rows completed successfully.")
else:
    for record in skipped:
        lines.append(f"- `{record['dataset']} + {record['system']}` was skipped. {record['notes']}")
    for record in failed:
        lines.append(f"- `{record['dataset']} + {record['system']}` failed. See the recorded command and log excerpt in the JSONL sidecar for debugging.")
lines.append("")
lines.append("## Reproduction")
lines.append("")
lines.append("```bash")
lines.append("export WMB_RUN_LLM_INTEGRATION=1")
lines.append("export LLM_MODEL=\"your-model\"")
lines.append("export LLM_API_KEY=\"your-key\"  # or set WMB_ALLOW_MISSING_LLM_API_KEY=1 for local no-auth endpoints")
lines.append("./scripts/reproduce_llm_smoke.sh")
lines.append("```")

report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {report_path}")
PY

if [[ $FAILURES -ne 0 ]]; then
  echo "LLM smoke report written with one or more failed rows." >&2
  exit 1
fi
