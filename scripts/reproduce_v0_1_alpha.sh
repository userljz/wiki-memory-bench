#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${WMB_REPORT_DIR:-$ROOT_DIR/reports}"
RESULTS_JSONL="$REPORT_DIR/.v0_1_alpha_results.jsonl"
RUN_IDS_FILE="$REPORT_DIR/v0.1-alpha-run-ids.txt"
# Final public report path: reports/v0.1-alpha-results.md
REPORT_FILE="$REPORT_DIR/v0.1-alpha-results.md"
SMOKE_ONLY="${WMB_SMOKE_ONLY:-0}"
SYNTHETIC_CASES="${WMB_SYNTHETIC_CASES:-100}"
SYNTHETIC_OUT="${WMB_SYNTHETIC_OUT:-data/synthetic/wiki_memory_100.jsonl}"

if [[ "$SMOKE_ONLY" == "1" && -z "${WMB_SYNTHETIC_CASES:-}" ]]; then
  SYNTHETIC_CASES="20"
fi

mkdir -p "$REPORT_DIR"
: > "$RESULTS_JSONL"
: > "$RUN_IDS_FILE"

TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
OS_SUMMARY="$(uname -a)"
if git rev-parse --git-dir >/dev/null 2>&1; then
  GIT_COMMIT_HASH="$(git rev-parse HEAD)"
  GIT_COMMIT_SHORT="$(git rev-parse --short HEAD)"
  GIT_STATUS_SUMMARY="$(git status --short || true)"
else
  GIT_COMMIT_HASH="unknown"
  GIT_COMMIT_SHORT="unknown"
  GIT_STATUS_SUMMARY="git metadata unavailable"
fi
if [[ -z "$GIT_STATUS_SUMMARY" ]]; then
  GIT_STATUS_SUMMARY="clean"
fi

if command -v uv >/dev/null 2>&1; then
  UV_VERSION="$(uv --version)"
else
  UV_VERSION="uv unavailable"
fi

PYTHON_VERSION="$(uv run python --version 2>&1)"
PACKAGE_VERSION="$(uv run python -c 'import wiki_memory_bench; print(wiki_memory_bench.__version__)')"
if uv run python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('sentence_transformers') else 1)" >/dev/null 2>&1; then
  VECTOR_DEPENDENCY_INSTALLED="true"
else
  VECTOR_DEPENDENCY_INSTALLED="false"
fi

echo "== Environment Info =="
echo "UTC Timestamp: $TIMESTAMP_UTC"
echo "Repository: $ROOT_DIR"
echo "Git commit: $GIT_COMMIT_HASH"
echo "OS: $OS_SUMMARY"
echo "Python: $PYTHON_VERSION"
echo "uv: $UV_VERSION"
echo "Package version: $PACKAGE_VERSION"
echo "Vector dependency installed: $VECTOR_DEPENDENCY_INSTALLED"

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
  local command_string="${cmd[*]}"

  echo
  echo "== Running: $command_string =="
  COMMANDS_RUN+=("$command_string")
  "${cmd[@]}"

  RESULTS_JSONL="$RESULTS_JSONL" \
  RUN_IDS_FILE="$RUN_IDS_FILE" \
  NOTES="$notes" \
  LIMITATIONS="$limitations" \
  ANSWERER="$answerer" \
  COMMAND_STRING="$command_string" \
  VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
  uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

benchmark_home = Path(os.environ.get("WMB_HOME", ".")).expanduser().resolve()
latest_run_dir = benchmark_home / "runs" / "latest"
summary_path = latest_run_dir / "summary.json"
manifest_path = latest_run_dir / "manifest.json"
predictions_path = latest_run_dir / "predictions.jsonl"

summary = json.loads(summary_path.read_text(encoding="utf-8"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
predictions = [
    json.loads(line)
    for line in predictions_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
metadata = predictions[0].get("metadata", {}) if predictions else {}
command_string = os.environ["COMMAND_STRING"]
command_parts = shlex.split(command_string)


def option_value(flag: str) -> str | None:
    try:
        index = command_parts.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(command_parts):
        return None
    return command_parts[index + 1]


def classify_gold_usage(system_name: str, metadata: dict[str, object]) -> tuple[str, bool, str]:
    mode = str(metadata.get("clipwiki_mode") or option_value("--mode") or "default")
    if system_name in {"full-context-oracle", "full-context"}:
        return (
            "oracle",
            True,
            "Deterministic multiple-choice mode uses the gold answer directly.",
        )
    if system_name == "clipwiki" and mode == "oracle-curated":
        return (
            "gold-evidence-selection",
            True,
            "Uses gold evidence/session labels to choose wiki source pages.",
        )
    return (
        "non-oracle",
        False,
        "No gold labels are used during retrieval or answering for this row.",
    )


def dependency_mode(system_name: str, vector_installed: bool) -> str:
    if system_name == "vector-rag":
        return "vector-extra-installed" if vector_installed else "vector-extra-missing"
    return "core"


def adapter_mode(system_name: str, metadata: dict[str, object]) -> str:
    if system_name == "basic-memory":
        return str(metadata.get("backend_mode", "unknown"))
    return "n/a"


oracle_label, uses_gold_labels, gold_usage_detail = classify_gold_usage(summary["system_name"], metadata)
mode = str(metadata.get("clipwiki_mode") or option_value("--mode") or "default")
answerer_mode = str(metadata.get("answerer_mode") or os.environ["ANSWERER"])
vector_installed = os.environ["VECTOR_DEPENDENCY_INSTALLED"].lower() == "true"

record = {
    "status": "ok",
    "dataset": summary["dataset_name"],
    "system": summary["system_name"],
    "mode": mode,
    "answerer": answerer_mode,
    "oracle_label": oracle_label,
    "uses_gold_labels": uses_gold_labels,
    "gold_usage_detail": gold_usage_detail,
    "external_adapter_mode": adapter_mode(summary["system_name"], metadata),
    "dependency_mode": dependency_mode(summary["system_name"], vector_installed),
    "vector_dependency_installed": vector_installed,
    "limit": manifest.get("limit"),
    "accuracy": summary.get("accuracy"),
    "citation_precision": summary.get("citation_precision"),
    "avg_latency_ms": summary.get("avg_latency_ms"),
    "avg_retrieved_tokens": summary.get("avg_retrieved_tokens"),
    "command": command_string,
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
    "run_id": manifest["run_id"],
    "run_dir": manifest["run_dir"],
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
  shift 6

  local cmd=("uv" "run" "wmb" "run" "--dataset" "$dataset" "--system" "$system" "--limit" "$limit")
  if [[ "$answerer" != "deterministic" ]]; then
    cmd+=("--answerer" "$answerer")
  fi
  if [[ "$#" -gt 0 ]]; then
    cmd+=("$@")
  fi
  local command_string="${cmd[*]}"

  RESULTS_JSONL="$RESULTS_JSONL" \
  NOTES="$notes" \
  LIMITATIONS="$limitations" \
  ANSWERER="$answerer" \
  DATASET="$dataset" \
  SYSTEM="$system" \
  LIMIT="$limit" \
  COMMAND_STRING="$command_string" \
  VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
  uv run python - <<'PY'
import json
import os
import shlex
from pathlib import Path

command_string = os.environ["COMMAND_STRING"]
command_parts = shlex.split(command_string)


def option_value(flag: str) -> str | None:
    try:
        index = command_parts.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(command_parts):
        return None
    return command_parts[index + 1]


def classify_gold_usage(system_name: str, mode: str) -> tuple[str, bool, str]:
    if system_name in {"full-context-oracle", "full-context"}:
        return (
            "oracle",
            True,
            "Deterministic multiple-choice mode uses the gold answer directly.",
        )
    if system_name == "clipwiki" and mode == "oracle-curated":
        return (
            "gold-evidence-selection",
            True,
            "Uses gold evidence/session labels to choose wiki source pages.",
        )
    return (
        "non-oracle",
        False,
        "No gold labels are used during retrieval or answering for this row.",
    )


system_name = os.environ["SYSTEM"]
mode = option_value("--mode") or "default"
vector_installed = os.environ["VECTOR_DEPENDENCY_INSTALLED"].lower() == "true"
oracle_label, uses_gold_labels, gold_usage_detail = classify_gold_usage(system_name, mode)

record = {
    "status": "skipped",
    "dataset": os.environ["DATASET"],
    "system": system_name,
    "mode": mode,
    "answerer": os.environ["ANSWERER"],
    "oracle_label": oracle_label,
    "uses_gold_labels": uses_gold_labels,
    "gold_usage_detail": gold_usage_detail,
    "external_adapter_mode": "n/a",
    "dependency_mode": "vector-extra-missing" if system_name == "vector-rag" else "core",
    "vector_dependency_installed": vector_installed,
    "limit": int(os.environ["LIMIT"]),
    "accuracy": None,
    "citation_precision": None,
    "avg_latency_ms": None,
    "avg_retrieved_tokens": None,
    "command": command_string,
    "notes": os.environ["NOTES"],
    "known_limitations": os.environ["LIMITATIONS"],
    "run_id": None,
    "run_dir": None,
}

results_path = Path(os.environ["RESULTS_JSONL"])
results_path.parent.mkdir(parents=True, exist_ok=True)
with results_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
PY
}

echo
echo "== Preparing deterministic synthetic dataset =="
COMMANDS_RUN+=("uv run wmb synthetic generate --cases $SYNTHETIC_CASES --out $SYNTHETIC_OUT")
uv run wmb synthetic generate --cases "$SYNTHETIC_CASES" --out "$SYNTHETIC_OUT"

run_case \
  "synthetic-mini" \
  "bm25" \
  "deterministic" \
  "5" \
  "Tiny smoke suite; useful for sanity checks, not a realistic long-memory benchmark." \
  "Too small to compare systems rigorously."

if [[ "$SMOKE_ONLY" != "1" ]]; then
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
    "Evidence-first wiki compiler and metadata-aware deterministic answer extraction." \
    "Multi-page synthesis is still heuristic and can miss some non-literal aggregations."

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
    "Deterministic wiki compiler in full-wiki mode with no oracle evidence selection." \
    "Page compilation and heuristic answer extraction still lose information relative to raw retrieval baselines." \
    "--mode" "full-wiki"
fi

COMMANDS_JSON="$(printf '%s\n' "${COMMANDS_RUN[@]}" | uv run python -c 'import json,sys; print(json.dumps(sys.stdin.read().splitlines()))')"
COMMANDS_JSON="$COMMANDS_JSON" \
RESULTS_JSONL="$RESULTS_JSONL" \
REPORT_FILE="$REPORT_FILE" \
RUN_IDS_FILE="$RUN_IDS_FILE" \
TIMESTAMP_UTC="$TIMESTAMP_UTC" \
ROOT_DIR="$ROOT_DIR" \
GIT_COMMIT_HASH="$GIT_COMMIT_HASH" \
GIT_COMMIT_SHORT="$GIT_COMMIT_SHORT" \
GIT_STATUS_SUMMARY="$GIT_STATUS_SUMMARY" \
OS_SUMMARY="$OS_SUMMARY" \
PYTHON_VERSION="$PYTHON_VERSION" \
UV_VERSION="$UV_VERSION" \
PACKAGE_VERSION="$PACKAGE_VERSION" \
VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
SYNTHETIC_CASES="$SYNTHETIC_CASES" \
SYNTHETIC_OUT="$SYNTHETIC_OUT" \
SMOKE_ONLY="$SMOKE_ONLY" \
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
timestamp_utc = os.environ["TIMESTAMP_UTC"]
root_dir = os.environ["ROOT_DIR"]
git_commit_hash = os.environ["GIT_COMMIT_HASH"]
git_commit_short = os.environ["GIT_COMMIT_SHORT"]
git_status_summary = os.environ["GIT_STATUS_SUMMARY"]
os_summary = os.environ["OS_SUMMARY"]
python_version = os.environ["PYTHON_VERSION"]
uv_version = os.environ["UV_VERSION"]
package_version = os.environ["PACKAGE_VERSION"]
vector_dependency_installed = os.environ["VECTOR_DEPENDENCY_INSTALLED"]
synthetic_cases = os.environ["SYNTHETIC_CASES"]
synthetic_out = os.environ["SYNTHETIC_OUT"]
smoke_only = os.environ["SMOKE_ONLY"] == "1"


def fmt_metric(value, pct: bool = False) -> str:
    if value is None:
        return "skipped"
    if pct:
        return f"{value * 100:.2f}%"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def dataset_notes() -> list[str]:
    rows = [
        "- `synthetic-mini`: built-in five-case smoke dataset. This row is useful for sanity checks, not for scientific comparison.",
        f"- `synthetic-wiki-memory`: generated locally via `uv run wmb synthetic generate --cases {synthetic_cases} --out {synthetic_out}` and evaluated with `--limit 50`.",
        "- `locomo-mc10`: loaded from `Percena/locomo-mc10:data/locomo_mc10.json` via the Hugging Face cache unless `WMB_LOCOMO_MC10_SOURCE_FILE` is set.",
    ]
    if smoke_only:
        rows.append("- Smoke mode was enabled for this report run; only the smoke subset was executed.")
    return rows


def failure_analysis(records: list[dict[str, object]]) -> list[str]:
    findings: list[str] = []

    for record in records:
        if record["status"] == "skipped":
            findings.append(
                f"- `{record['dataset']} + {record['system']}` was skipped because the required dependency mode was unavailable. "
                f"Command retained: `{record['command']}`."
            )

    for record in records:
        if record["status"] != "ok":
            continue
        accuracy = record.get("accuracy")
        citation_precision = record.get("citation_precision")
        if accuracy is not None and accuracy < 0.4:
            findings.append(
                f"- `{record['dataset']} + {record['system']}` is a weak alpha row: accuracy is only "
                f"{fmt_metric(accuracy, pct=True)} and citation precision is {fmt_metric(citation_precision, pct=True)}."
            )
        elif citation_precision is not None and citation_precision < 0.1:
            findings.append(
                f"- `{record['dataset']} + {record['system']}` answers some questions correctly but grounding is weak: "
                f"citation precision is {fmt_metric(citation_precision, pct=True)}."
            )

    if git_status_summary != "clean":
        findings.append(
            "- The working tree was dirty when this report was produced. Reproducing the exact numbers requires the same commit plus the local diff shown below."
        )

    return findings or ["- No additional failure analysis notes were generated for this run."]


lines: list[str] = []
lines.append("# v0.1-alpha Results")
lines.append("")
lines.append("This report is generated by `scripts/reproduce_v0_1_alpha.sh` and is intended to be an honest, reproducible alpha snapshot.")
lines.append("")
lines.append("## Environment")
lines.append("")
lines.extend(
    [
        f"- git commit: `{git_commit_hash}` (`{git_commit_short}`)",
        f"- repository root: `{root_dir}`",
        f"- timestamp (UTC): `{timestamp_utc}`",
        f"- package version: `{package_version}`",
        f"- Python: `{python_version}`",
        f"- uv: `{uv_version}`",
        f"- OS: `{os_summary}`",
        f"- vector dependency installed: `{vector_dependency_installed}`",
    ]
)
lines.append("")
lines.append("### Git Status Summary")
lines.append("")
lines.append("```text")
lines.extend(git_status_summary.splitlines())
lines.append("```")
lines.append("")
lines.append("## Commands Run")
lines.append("")
for command in commands:
    lines.append(f"- `{command}`")
lines.append("")
lines.append("## Datasets")
lines.append("")
lines.extend(dataset_notes())
lines.append("")
lines.append("## Result Table")
lines.append("")
lines.append("| Dataset | System | Mode | Answerer | Oracle Label | Uses Gold Labels | Adapter Mode | Dependency Mode | Status | Accuracy | Citation Precision | Avg Latency (ms) | Avg Retrieved Tokens | Run ID |")
lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
for record in records:
    lines.append(
        "| {dataset} | {system} | {mode} | {answerer} | {oracle_label} | {uses_gold_labels} | {external_adapter_mode} | {dependency_mode} | {status} | {accuracy} | {citation_precision} | {latency} | {retrieved} | {run_id} |".format(
            dataset=record["dataset"],
            system=record["system"],
            mode=record["mode"],
            answerer=record["answerer"],
            oracle_label=record["oracle_label"],
            uses_gold_labels="yes" if record["uses_gold_labels"] else "no",
            external_adapter_mode=record["external_adapter_mode"],
            dependency_mode=record["dependency_mode"],
            status=record["status"],
            accuracy=fmt_metric(record["accuracy"], pct=True),
            citation_precision=fmt_metric(record["citation_precision"], pct=True),
            latency=fmt_metric(record["avg_latency_ms"]),
            retrieved=fmt_metric(record["avg_retrieved_tokens"]),
            run_id=record["run_id"] or "skipped",
        )
    )
lines.append("")
lines.append("## Exact Commands")
lines.append("")
for record in records:
    lines.append(f"- `{record['dataset']} + {record['system']}` [{record['status']}]: `{record['command']}`")
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
lines.append("## Oracle / Non-Oracle Explanation")
lines.append("")
lines.append("- `oracle`: the row uses gold labels directly at runtime. If `full-context-oracle` appears in any future table, it must be interpreted as an upper bound rather than a fair deployable baseline.")
lines.append("- `gold-evidence-selection`: the row uses gold evidence labels to choose retrieval context. A typical example is `clipwiki --mode oracle-curated`.")
lines.append("- `non-oracle`: the row does not use gold labels during retrieval or answering. All rows in this v0.1-alpha table are intended to be interpreted under this label unless marked otherwise.")
lines.append("")
lines.append("## Limitations")
lines.append("")
lines.append("- These are alpha benchmark artifacts, not final scientific claims.")
lines.append("- `synthetic-mini` is a smoke benchmark with only five examples.")
lines.append("- `synthetic-wiki-memory` and `locomo-mc10` rows here are limited-slice alpha runs, not exhaustive leaderboard measurements.")
lines.append("- Optional dependency rows depend on the local environment; `vector-rag` is only run when the vector stack is installed.")
lines.append("- Poor-performing rows are intentionally retained. This report does not hide failures to improve presentation.")
lines.append("")
lines.append("## Failure Analysis")
lines.append("")
lines.extend(failure_analysis(records))
lines.append("")
lines.append("## Reproduction Commands")
lines.append("")
lines.append("```bash")
lines.append("uv sync --group dev")
lines.append("uv sync --group dev --extra vector  # required if you want the vector-rag row")
lines.append("./scripts/reproduce_v0_1_alpha.sh")
lines.append("```")
lines.append("")
lines.append("The exact per-row commands executed for this report are listed above in `Exact Commands`.")

report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {report_path}")
PY

echo
echo "== Done =="
echo "Run IDs saved to: $RUN_IDS_FILE"
echo "Combined report written to: $REPORT_FILE"
