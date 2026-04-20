#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_DIR="$ROOT_DIR/reports"
RESULTS_JSONL="$REPORT_DIR/.v0_1_alpha_results.jsonl"
RUN_IDS_FILE="$REPORT_DIR/v0.1-alpha-run-ids.txt"
# Final public report path: reports/v0.1-alpha-results.md
REPORT_FILE="$REPORT_DIR/v0.1-alpha-results.md"

mkdir -p "$REPORT_DIR"
: > "$RESULTS_JSONL"
: > "$RUN_IDS_FILE"

echo "== Environment Info =="
date -u +"UTC Timestamp: %Y-%m-%dT%H:%M:%SZ"
echo "Repository: $ROOT_DIR"
echo "OS: $(uname -a)"
echo "Python: $(uv run python --version)"
echo "uv: $(uv --version)"
echo "Package version: $(uv run python -c 'import wiki_memory_bench; print(wiki_memory_bench.__version__)')"

COMMANDS_RUN=()

run_case() {
  local dataset="$1"
  local system="$2"
  local answerer="$3"
  local limit="$4"
  local notes="$5"
  local limitations="$6"
  shift 6

  local cmd=("uv" "run" "wmb" "run" "--dataset" "$dataset" "--system" "$system" "--limit" "$limit")
  if [[ "$answerer" != "deterministic" ]]; then
    cmd+=("--answerer" "$answerer")
  fi
  if [[ "$#" -gt 0 ]]; then
    cmd+=("$@")
  fi

  echo
  echo "== Running: ${cmd[*]} =="
  COMMANDS_RUN+=("${cmd[*]}")
  "${cmd[@]}"

  RESULTS_JSONL="$RESULTS_JSONL" RUN_IDS_FILE="$RUN_IDS_FILE" NOTES="$notes" LIMITATIONS="$limitations" ANSWERER="$answerer" \
  uv run python - <<'PY'
import json
import os
from pathlib import Path

summary_path = Path("runs/latest/summary.json")
manifest_path = Path("runs/latest/manifest.json")
summary = json.loads(summary_path.read_text(encoding="utf-8"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

record = {
    "dataset": summary["dataset_name"],
    "system": summary["system_name"],
    "answerer": os.environ["ANSWERER"],
    "limit": manifest.get("limit"),
    "accuracy": summary.get("accuracy"),
    "citation_precision": summary.get("citation_precision"),
    "avg_latency_ms": summary.get("avg_latency_ms"),
    "avg_retrieved_tokens": summary.get("avg_retrieved_tokens"),
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
    "run_id": manifest["run_id"],
}

results_path = Path(os.environ["RESULTS_JSONL"])
results_path.parent.mkdir(parents=True, exist_ok=True)
with results_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")

run_ids_path = Path(os.environ["RUN_IDS_FILE"])
with run_ids_path.open("a", encoding="utf-8") as handle:
    handle.write(f"{record['run_id']}\t{record['dataset']}\t{record['system']}\n")
PY
}

append_skipped_case() {
  local dataset="$1"
  local system="$2"
  local answerer="$3"
  local limit="$4"
  local notes="$5"
  local limitations="$6"
  COMMANDS_RUN+=("SKIPPED ${system} on ${dataset}")

  RESULTS_JSONL="$RESULTS_JSONL" NOTES="$notes" LIMITATIONS="$limitations" ANSWERER="$answerer" DATASET="$dataset" SYSTEM="$system" LIMIT="$limit" \
  uv run python - <<'PY'
import json
import os
from pathlib import Path

record = {
    "dataset": os.environ["DATASET"],
    "system": os.environ["SYSTEM"],
    "answerer": os.environ["ANSWERER"],
    "limit": int(os.environ["LIMIT"]),
    "accuracy": None,
    "citation_precision": None,
    "avg_latency_ms": None,
    "avg_retrieved_tokens": None,
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
    "run_id": None,
}

results_path = Path(os.environ["RESULTS_JSONL"])
results_path.parent.mkdir(parents=True, exist_ok=True)
with results_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
PY
}

echo
echo "== Preparing deterministic synthetic dataset =="
COMMANDS_RUN+=("uv run wmb synthetic generate --cases 100 --out data/synthetic/wiki_memory_100.jsonl")
uv run wmb synthetic generate --cases 100 --out data/synthetic/wiki_memory_100.jsonl

run_case \
  "synthetic-mini" \
  "bm25" \
  "deterministic" \
  "5" \
  "Tiny smoke suite; useful for sanity checks, not a realistic long-memory benchmark." \
  "Too small to compare systems rigorously."

run_case \
  "synthetic-wiki-memory" \
  "bm25" \
  "deterministic" \
  "50" \
  "Deterministic open-QA extraction over retrieved notes." \
  "Does not model wiki maintenance operations explicitly."

run_case \
  "synthetic-wiki-memory" \
  "clipwiki" \
  "deterministic" \
  "50" \
  "Deterministic wiki compiler and page retrieval; good for debugging failure modes." \
  "Synthetic maintenance tasks remain difficult for heuristic answer extraction."

run_case \
  "locomo-mc10" \
  "bm25" \
  "deterministic" \
  "50" \
  "Lexical retrieval over session summaries and full sessions." \
  "No learned reranking; sensitive to wording and long-session noise."

if uv run python -c "import sentence_transformers" >/dev/null 2>&1; then
  run_case \
    "locomo-mc10" \
    "vector-rag" \
    "deterministic" \
    "50" \
    "Local embedding baseline with in-memory index." \
    "First run may be slower because embeddings and model weights are loaded locally."
else
  append_skipped_case \
    "locomo-mc10" \
    "vector-rag" \
    "deterministic" \
    "50" \
    "Skipped because vector dependencies are not installed." \
    "Install the optional vector stack to reproduce this row."
fi

run_case \
  "locomo-mc10" \
  "clipwiki" \
  "deterministic" \
  "50" \
  "Deterministic wiki compiler with oracle-curated mode not used here; this run reflects the default full-wiki mode." \
  "Page compilation and heuristic answer extraction still lose information relative to raw retrieval baselines." \
  "--mode" "full-wiki"

COMMANDS_JSON="$(printf '%s\n' "${COMMANDS_RUN[@]}" | uv run python -c 'import json,sys; print(json.dumps(sys.stdin.read().splitlines()))')"
COMMANDS_JSON="$COMMANDS_JSON" RESULTS_JSONL="$RESULTS_JSONL" REPORT_FILE="$REPORT_FILE" RUN_IDS_FILE="$RUN_IDS_FILE" \
uv run python - <<'PY'
import json
import os
from pathlib import Path

results_path = Path(os.environ["RESULTS_JSONL"])
report_path = Path(os.environ["REPORT_FILE"])
run_ids_path = Path(os.environ["RUN_IDS_FILE"])
commands = json.loads(os.environ["COMMANDS_JSON"])
records = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
run_ids = run_ids_path.read_text(encoding="utf-8").strip()

lines: list[str] = []
lines.append("# v0.1-alpha Results")
lines.append("")
lines.append("This report is generated by `scripts/reproduce_v0_1_alpha.sh` and is intended to be an honest, reproducible alpha snapshot.")
lines.append("")
lines.append("## Commands Run")
lines.append("")
for command in commands:
    lines.append(f"- `{command}`")
lines.append("")
lines.append("## Run IDs")
lines.append("")
if run_ids:
    lines.append("```text")
    lines.extend(run_ids.splitlines())
    lines.append("```")
else:
    lines.append("No run IDs were recorded.")
lines.append("")
lines.append("## Result Table")
lines.append("")
lines.append("| Dataset | System | Answerer | Limit | Accuracy | Citation Precision | Avg Latency (ms) | Avg Retrieved Tokens | Notes | Known Limitations |")
lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |")

for record in records:
    def fmt(value, pct=False):
        if value is None:
            return "skipped"
        if pct:
            return f"{value * 100:.2f}%"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    lines.append(
        "| {dataset} | {system} | {answerer} | {limit} | {accuracy} | {citation_precision} | {latency} | {retrieved} | {notes} | {limitations} |".format(
            dataset=record["dataset"],
            system=record["system"],
            answerer=record["answerer"],
            limit=record["limit"],
            accuracy=fmt(record["accuracy"], pct=True),
            citation_precision=fmt(record["citation_precision"], pct=True),
            latency=fmt(record["avg_latency_ms"]),
            retrieved=fmt(record["avg_retrieved_tokens"]),
            notes=record["notes"],
            limitations=record["known_limitations"],
        )
    )

lines.append("")
lines.append("## Interpretation Notes")
lines.append("")
lines.append("- These results are benchmark artifacts for research and development, not product claims.")
lines.append("- Poor-performing rows are intentionally kept in the table. No rows are removed to improve presentation.")
lines.append("- Deterministic baselines are useful for reproducibility but may understate or overstate what a stronger learned answerer could do.")

report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {report_path}")
PY

echo
echo "== Done =="
echo "Run IDs saved to: $RUN_IDS_FILE"
echo "Combined report written to: $REPORT_FILE"
