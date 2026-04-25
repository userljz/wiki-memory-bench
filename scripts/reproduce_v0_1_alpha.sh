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
ALLOW_DIRTY_REPORT="${WMB_ALLOW_DIRTY_REPORT:-0}"

if [[ "$SMOKE_ONLY" == "1" && -z "${WMB_SYNTHETIC_CASES:-}" ]]; then
  SYNTHETIC_CASES="20"
fi

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

EVALUATED_SOURCE_COMMIT="${WMB_EVALUATED_SOURCE_COMMIT:-$GIT_COMMIT_HASH}"

if [[ "$GIT_STATUS_SUMMARY" != "clean" && "$ALLOW_DIRTY_REPORT" != "1" ]]; then
  echo "Refusing to generate public report from dirty working tree." >&2
  exit 1
fi

mkdir -p "$REPORT_DIR"
: > "$RESULTS_JSONL"
: > "$RUN_IDS_FILE"

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
echo "Evaluated source commit: $EVALUATED_SOURCE_COMMIT"
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
    if "uses_gold_labels" in metadata:
        uses_gold_labels = bool(metadata.get("uses_gold_labels"))
        oracle_label = str(metadata.get("oracle_label") or ("oracle" if uses_gold_labels else "non-oracle"))
        fields = metadata.get("gold_label_fields_used", [])
        detail = (
            f"System metadata reports gold label fields used: {fields}."
            if uses_gold_labels
            else "System metadata reports no gold labels are used during retrieval or answering for this row."
        )
        return oracle_label, uses_gold_labels, detail
    if system_name in {"full-context-oracle", "full-context"}:
        return (
            "oracle-upper-bound",
            True,
            "Deterministic multiple-choice mode uses the gold answer directly.",
        )
    if system_name == "clipwiki" and mode == "oracle-curated":
        return (
            "oracle-upper-bound",
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
dataset_metadata = manifest.get("dataset_metadata", {})
requested_config = dataset_metadata.get("requested_config", {})
prepared_cache = dataset_metadata.get("prepared_cache", {})
source_metadata = dataset_metadata.get("source_metadata") or prepared_cache.get("source") or {}

record = {
    "status": "ok",
    "dataset": summary["dataset_name"],
    "split": requested_config.get("split") or "default",
    "system": summary["system_name"],
    "mode": mode,
    "answerer": answerer_mode,
    "judge": manifest.get("judge", "deterministic"),
    "oracle_label": oracle_label,
    "uses_gold_labels": uses_gold_labels,
    "gold_usage_detail": gold_usage_detail,
    "system_options": manifest.get("system_options", {}),
    "external_adapter_mode": adapter_mode(summary["system_name"], metadata),
    "dependency_mode": dependency_mode(summary["system_name"], vector_installed),
    "vector_dependency_installed": vector_installed,
    "limit": manifest.get("limit"),
    "examples": summary.get("example_count"),
    "completed_count": summary.get("completed_count"),
    "error_count": summary.get("error_count"),
    "error_rate": summary.get("error_rate"),
    "accuracy": summary.get("accuracy"),
    "citation_precision": summary.get("citation_precision"),
    "citation_source_precision": summary.get("citation_source_precision"),
    "citation_source_recall": summary.get("citation_source_recall"),
    "citation_source_f1": summary.get("citation_source_f1"),
    "stale_citation_rate": summary.get("stale_citation_rate"),
    "unsupported_answer_rate": summary.get("unsupported_answer_rate"),
    "answer_correct_but_bad_citation_rate": summary.get("answer_correct_but_bad_citation_rate"),
    "avg_latency_ms": summary.get("avg_latency_ms"),
    "avg_retrieved_tokens": summary.get("avg_retrieved_tokens"),
    "avg_wiki_tokens": summary.get("avg_wiki_size_tokens"),
    "dataset_source": source_metadata,
    "prepared_cache": prepared_cache,
    "error_policy": manifest.get("error_policy"),
    "dependency_versions": manifest.get("dependency_versions", {}),
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
            "oracle-upper-bound",
            True,
            "Deterministic multiple-choice mode uses the gold answer directly.",
        )
    if system_name == "clipwiki" and mode == "oracle-curated":
        return (
            "oracle-upper-bound",
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
    "split": "default",
    "system": system_name,
    "mode": mode,
    "answerer": os.environ["ANSWERER"],
    "judge": "deterministic",
    "oracle_label": oracle_label,
    "uses_gold_labels": uses_gold_labels,
    "gold_usage_detail": gold_usage_detail,
    "system_options": {"mode": mode} if mode != "default" else {},
    "external_adapter_mode": "n/a",
    "dependency_mode": "vector-extra-missing" if system_name == "vector-rag" else "core",
    "vector_dependency_installed": vector_installed,
    "limit": int(os.environ["LIMIT"]),
    "examples": None,
    "completed_count": 0,
    "error_count": None,
    "error_rate": None,
    "accuracy": None,
    "citation_precision": None,
    "citation_source_precision": None,
    "citation_source_recall": None,
    "citation_source_f1": None,
    "stale_citation_rate": None,
    "unsupported_answer_rate": None,
    "answer_correct_but_bad_citation_rate": None,
    "avg_latency_ms": None,
    "avg_retrieved_tokens": None,
    "avg_wiki_tokens": None,
    "dataset_source": {},
    "prepared_cache": {},
    "error_policy": "fail_fast",
    "dependency_versions": {},
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

run_case \
  "synthetic-mini" \
  "full-context-oracle" \
  "deterministic" \
  "5" \
  "Oracle upper-bound smoke row; verifies gold-label metadata is surfaced in artifacts." \
  "Uses gold labels directly and is excluded from fair non-oracle comparisons."

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
EVALUATED_SOURCE_COMMIT="$EVALUATED_SOURCE_COMMIT" \
OS_SUMMARY="$OS_SUMMARY" \
PYTHON_VERSION="$PYTHON_VERSION" \
UV_VERSION="$UV_VERSION" \
PACKAGE_VERSION="$PACKAGE_VERSION" \
VECTOR_DEPENDENCY_INSTALLED="$VECTOR_DEPENDENCY_INSTALLED" \
SYNTHETIC_CASES="$SYNTHETIC_CASES" \
SYNTHETIC_OUT="$SYNTHETIC_OUT" \
SMOKE_ONLY="$SMOKE_ONLY" \
WMB_ALLOW_DIRTY_REPORT="$ALLOW_DIRTY_REPORT" \
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
evaluated_source_commit = os.environ["EVALUATED_SOURCE_COMMIT"]
os_summary = os.environ["OS_SUMMARY"]
python_version = os.environ["PYTHON_VERSION"]
uv_version = os.environ["UV_VERSION"]
package_version = os.environ["PACKAGE_VERSION"]
vector_dependency_installed = os.environ["VECTOR_DEPENDENCY_INSTALLED"]
synthetic_cases = os.environ["SYNTHETIC_CASES"]
synthetic_out = os.environ["SYNTHETIC_OUT"]
smoke_only = os.environ["SMOKE_ONLY"] == "1"
allow_dirty_report = os.environ["WMB_ALLOW_DIRTY_REPORT"] == "1"
source_tree_status = "clean" if git_status_summary == "clean" else "dirty"
if source_tree_status == "clean":
    report_file_commit_note = (
        "The source tree was clean at report generation time. "
        "The report file may be committed in a later commit."
    )
else:
    report_file_commit_note = (
        "WARNING: This report was generated from a dirty source tree with "
        "WMB_ALLOW_DIRTY_REPORT=1. The evaluated_source_commit alone is not "
        "sufficient to reproduce the report; the local working-tree diff listed "
        "below is also part of the evaluated state."
    )


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


def dataset_source_notes(records: list[dict[str, object]]) -> list[str]:
    rows: list[str] = []
    for record in records:
        source = record.get("dataset_source") or {}
        cache = record.get("prepared_cache") or {}
        if isinstance(source, dict):
            source_id = source.get("identifier") or source.get("path") or "not recorded"
            checksum = source.get("checksum_sha256") or "not recorded"
        else:
            source_id = "not recorded"
            checksum = "not recorded"
        cache_request = cache.get("request") if isinstance(cache, dict) else None
        rows.append(
            f"- `{record['dataset']} + {record['system']}`: source=`{source_id}`, checksum=`{checksum}`, prepared_cache_request=`{cache_request or 'not used'}`"
        )
    return rows


def system_option_notes(records: list[dict[str, object]]) -> list[str]:
    return [
        f"- `{record['dataset']} + {record['system']}`: system_options=`{record.get('system_options', {})}`, answerer=`{record.get('answerer')}`, judge=`{record.get('judge')}`, error_policy=`{record.get('error_policy', 'fail_fast')}`"
        for record in records
    ]


def dependency_version_notes(records: list[dict[str, object]]) -> list[str]:
    for record in records:
        versions = record.get("dependency_versions")
        if isinstance(versions, dict) and versions:
            return [f"- `{key}`: `{value if value is not None else 'not installed'}`" for key, value in sorted(versions.items())]
    return ["- Structured dependency versions were not recorded for these rows."]


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

    if git_status_summary != "clean" and allow_dirty_report:
        findings.append(
            "- The working tree was dirty when this report was produced. Reproducing the exact numbers requires the same commit plus the local diff shown below."
        )

    return findings or ["- No additional failure analysis notes were generated for this run."]


def summarize_vector_rag(records: list[dict[str, object]]) -> str:
    vector_rows = [record for record in records if record["system"] == "vector-rag"]
    if not vector_rows:
        if smoke_only:
            return "`not-scheduled` (smoke mode does not include the `vector-rag` row)."
        return "`not-scheduled` (no `vector-rag` row was part of this report)."

    record = vector_rows[0]
    if record["status"] == "ok":
        return (
            f"`ran` (`status={record['status']}`, "
            f"`dependency_mode={record['dependency_mode']}`)"
        )
    return (
        f"`skipped` (`status={record['status']}`, "
        f"`dependency_mode={record['dependency_mode']}`)"
    )


def summarize_gold_label_usage(records: list[dict[str, object]]) -> tuple[str, str]:
    gold_rows = [
        f"`{record['dataset']} + {record['system']} ({record['mode']})`"
        for record in records
        if record["uses_gold_labels"]
    ]
    if not gold_rows:
        return "`no`", "none"
    return "`yes`", ", ".join(gold_rows)


lines: list[str] = []
lines.append("# v0.1-alpha Technical Report")
lines.append("")
lines.append("This report is generated by `scripts/reproduce_v0_1_alpha.sh` and is intended to be an honest, reproducible alpha snapshot. It emphasizes benchmark protocol, provenance, and limitations rather than leaderboard claims.")
lines.append("")
any_rows_use_gold_labels, rows_using_gold_labels = summarize_gold_label_usage(records)
vector_rag_status = summarize_vector_rag(records)

lines.append("## Provenance")
lines.append("")
lines.extend(
    [
        f"- evaluated_source_commit: `{evaluated_source_commit}`",
        f"- report_generated_at: `{timestamp_utc}`",
        f"- source_tree_status_at_generation: `{source_tree_status}`",
        f"- report_file_commit_note: {report_file_commit_note}",
    ]
)
lines.append("")
if git_status_summary != "clean":
    lines.append("### Dirty Source Warning")
    lines.append("")
    lines.append("```text")
    lines.append("WARNING: WMB_ALLOW_DIRTY_REPORT=1 was set.")
    lines.append("This report includes uncommitted local changes in addition to the evaluated source commit.")
    lines.append("Do not interpret evaluated_source_commit as a complete reproduction reference without the dirty tree details below.")
    lines.append("```")
    lines.append("")
    lines.append("### Source Tree Details")
    lines.append("")
    lines.append("```text")
    lines.extend(git_status_summary.splitlines())
    lines.append("```")
    lines.append("")
lines.append("## Environment")
lines.append("")
lines.extend(
    [
        f"- package version: `{package_version}`",
        f"- Python: `{python_version}`",
        f"- uv: `{uv_version}`",
        f"- OS: `{os_summary}`",
        f"- vector dependency installed: `{vector_dependency_installed}`",
    ]
)
lines.append("")
lines.append("### Dependency Versions")
lines.append("")
lines.extend(dependency_version_notes(records))
lines.append("")
lines.append("## Benchmark Protocol")
lines.append("")
lines.append("- Deterministic no-key evaluation is the default path.")
lines.append("- Rows use deterministic answerers and deterministic judges unless explicitly stated otherwise.")
lines.append("- Oracle rows are upper bounds and are excluded from fair non-oracle comparisons.")
lines.append("- Optional LLM calibration is reported separately and is not part of this deterministic alpha table.")
lines.append("- All commands are listed exactly below; run artifacts are saved under `runs/` with manifests, summaries, predictions, and system artifacts.")
lines.append("")
lines.append("## Execution Summary")
lines.append("")
lines.extend(
    [
        f"- vector_rag_status: {vector_rag_status}",
        f"- any_rows_use_gold_labels: {any_rows_use_gold_labels}",
        f"- rows_using_gold_labels: {rows_using_gold_labels}",
    ]
)
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
lines.append("## Dataset Source And Prepared Cache Config")
lines.append("")
lines.extend(dataset_source_notes(records))
lines.append("")
lines.append("## System Options And Modes")
lines.append("")
lines.extend(system_option_notes(records))
lines.append("")
lines.append("## Result Table")
lines.append("")
lines.append("| Dataset | Split | System | Mode | Answerer | Judge | Oracle Label | Examples | Accuracy | Citation Source F1 | Stale Citation Rate | Unsupported Answer Rate | Error Rate | Avg Latency (ms) | Avg Retrieved Tokens | Avg Wiki Tokens | Dependency Mode | Uses Gold Labels | Status |")
lines.append("| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |")
for record in records:
    lines.append(
        "| {dataset} | {split} | {system} | {mode} | {answerer} | {judge} | {oracle_label} | {examples} | {accuracy} | {citation_source_f1} | {stale_citation_rate} | {unsupported_answer_rate} | {error_rate} | {latency} | {retrieved} | {wiki_tokens} | {dependency_mode} | {uses_gold_labels} | {status} |".format(
            dataset=record["dataset"],
            split=record.get("split", "default"),
            system=record["system"],
            mode=record["mode"],
            answerer=record.get("answerer", "deterministic"),
            judge=record.get("judge", "deterministic"),
            oracle_label=record.get("oracle_label", "non-oracle"),
            examples=fmt_metric(record.get("examples")),
            uses_gold_labels="yes" if record["uses_gold_labels"] else "no",
            dependency_mode=record["dependency_mode"],
            status=record["status"],
            accuracy=fmt_metric(record["accuracy"], pct=True),
            citation_source_f1=fmt_metric(record.get("citation_source_f1"), pct=True),
            stale_citation_rate=fmt_metric(record.get("stale_citation_rate"), pct=True),
            unsupported_answer_rate=fmt_metric(record.get("unsupported_answer_rate"), pct=True),
            error_rate=fmt_metric(record.get("error_rate"), pct=True),
            latency=fmt_metric(record["avg_latency_ms"]),
            retrieved=fmt_metric(record["avg_retrieved_tokens"]),
            wiki_tokens=fmt_metric(record.get("avg_wiki_tokens")),
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
lines.append("- `non-oracle`: the row does not use gold labels during retrieval or answering. These rows are eligible for fair system-to-system comparisons within the limits of the benchmark slice.")
lines.append("- `oracle-upper-bound`: the row uses gold labels directly at runtime and must be interpreted only as an upper bound, not as a deployable baseline.")
lines.append("- `full-context-oracle` is an oracle upper-bound system and is excluded from fair non-oracle comparisons.")
lines.append("- `clipwiki --mode oracle-curated` is also labeled `oracle-upper-bound` because it uses gold evidence labels to choose retrieval context.")
lines.append("- `full-wiki` and `curated` ClipWiki modes are non-oracle modes. They must not read `gold_evidence`, `answer_session_ids`, or `has_answer` labels.")
lines.append("")
lines.append("## Limitations")
lines.append("")
lines.append("- These are alpha benchmark artifacts, not final scientific claims.")
lines.append("- `synthetic-mini` is a smoke benchmark with only five examples.")
lines.append("- `synthetic-wiki-memory` and `locomo-mc10` rows here are limited-slice alpha runs, not exhaustive leaderboard measurements.")
lines.append("- Optional dependency rows depend on the local environment; `vector-rag` is only run when the vector stack is installed.")
lines.append("- Poor-performing rows are intentionally retained. This report does not hide failures to improve presentation.")
lines.append("- Citation source metrics are only as good as the available `expected_source_ids`; rows without source ids may rely on quote fallback behavior.")
lines.append("")
lines.append("## What This Benchmark Does Not Prove")
lines.append("")
lines.append("- It does not establish that ClipWiki is superior to vector RAG or any other baseline.")
lines.append("- It does not establish a production leaderboard.")
lines.append("- It does not measure all possible memory architectures, retrieval stacks, or LLM providers.")
lines.append("- It does not replace larger-scale human or real-world agent memory evaluation.")
lines.append("")
lines.append("## Failure Analysis")
lines.append("")
lines.extend(failure_analysis(records))
lines.append("")
lines.append("## Per-System Failure Analysis")
lines.append("")
for record in records:
    lines.append(f"- `{record['dataset']} + {record['system']}`: status=`{record['status']}`, accuracy=`{fmt_metric(record.get('accuracy'), pct=True)}`, citation_source_f1=`{fmt_metric(record.get('citation_source_f1'), pct=True)}`, stale_citation_rate=`{fmt_metric(record.get('stale_citation_rate'), pct=True)}`. Notes: {record.get('known_limitations', '')}")
lines.append("")
lines.append("## Next Steps")
lines.append("")
lines.append("- Re-run this report from a clean release commit before treating it as a final public artifact.")
lines.append("- Expand source-aware citation coverage for public datasets where evidence ids are available.")
lines.append("- Keep optional LLM calibration separate from deterministic no-key results.")
lines.append("- Add broader LongMemEval and external adapter coverage only after preserving provenance and fair-comparison boundaries.")
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
