"""Deterministic synthetic diagnostic dataset for wiki-style memory systems."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from wiki_memory_bench.datasets.base import DatasetAdapter, register_dataset
from wiki_memory_bench.schemas import EvalCase, HistoryClip, PreparedDataset, SessionTurn, TaskType
from wiki_memory_bench.utils.paths import resolve_user_path, synthetic_data_dir

TASK_TYPES = [
    "direct_recall",
    "update_latest_fact",
    "stale_claim_avoidance",
    "explicit_forgetting",
    "conflicting_sources",
    "multi_source_aggregation",
    "temporal_question",
    "citation_required",
    "abstention_when_not_in_memory",
    "paraphrased_question",
]

PEOPLE = ["Avery", "Morgan", "Jordan", "Taylor", "Riley", "Casey", "Quinn", "Skyler", "Parker", "Jamie"]
TOOLS = ["PostgreSQL", "Redis", "SQLite", "DuckDB", "Obsidian", "Neovim", "VS Code", "Emacs"]
CITIES = ["Seattle", "Austin", "Denver", "Boston", "Portland", "Chicago", "Toronto", "Vancouver"]
PROJECTS = ["Aurora", "Northstar", "Maple", "Comet", "Harbor", "Juniper", "Orbit", "Voyager"]
HOBBIES = ["trail running", "pottery", "birdwatching", "guitar", "kayaking", "photography"]
FOODS = ["ramen", "tacos", "sushi", "pho", "pasta", "dumplings"]


def default_synthetic_wiki_memory_path() -> Path:
    """Return the default export path for the synthetic wiki-memory dataset."""

    return synthetic_data_dir() / "wiki_memory_100.jsonl"


def generate_synthetic_wiki_memory_cases(cases: int = 100, seed: int = 42) -> list[dict[str, Any]]:
    """Generate deterministic wiki-style memory cases."""

    rng = random.Random(seed)
    generated: list[dict[str, Any]] = []
    for index in range(cases):
        task_type = TASK_TYPES[index % len(TASK_TYPES)]
        case_number = index + 1
        generated.append(_build_case(task_type=task_type, case_number=case_number, rng=rng))
    return generated


def export_synthetic_wiki_memory(cases: int, out_path: Path, seed: int = 42) -> Path:
    """Generate and export the synthetic wiki-memory dataset as JSONL."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = generate_synthetic_wiki_memory_cases(cases=cases, seed=seed)
    out_path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return out_path


def convert_synthetic_case(record: dict[str, Any], dataset_name: str = "synthetic-wiki-memory") -> EvalCase:
    """Convert a raw synthetic diagnostic case into the internal eval schema."""

    history_clips: list[HistoryClip] = []
    haystack_sessions: list[list[SessionTurn]] = []
    haystack_session_ids: list[str] = []
    haystack_session_datetimes: list[datetime] = []
    haystack_session_summaries: list[str] = []

    for session in record["sessions"]:
        session_id = str(session["session_id"])
        session_datetime = datetime.fromisoformat(str(session["timestamp"]))
        summary = str(session.get("summary", ""))
        session_turns = [
            SessionTurn(role=str(message["speaker"]), content=str(message["text"]))
            for message in session["messages"]
        ]
        haystack_sessions.append(session_turns)
        haystack_session_ids.append(session_id)
        haystack_session_datetimes.append(session_datetime)
        haystack_session_summaries.append(summary)

        for message in session["messages"]:
            message_timestamp = datetime.fromisoformat(str(message.get("timestamp", session["timestamp"])))
            history_clips.append(
                HistoryClip(
                    clip_id=str(message["message_id"]),
                    conversation_id=str(record["case_id"]),
                    session_id=session_id,
                    speaker=str(message["speaker"]),
                    timestamp=message_timestamp,
                    text=str(message["text"]),
                    source_ref=session_id,
                    metadata={"task_type": record["task_type"]},
                )
            )

    question_type = str(record.get("question_type", record["task_type"]))
    memory_operations = list(record.get("memory_operations", record.get("memory_operation_labels", [])))
    generation_template_id = str(record.get("generation_template_id", f"legacy:{record['task_type']}"))

    return EvalCase(
        example_id=str(record["case_id"]),
        dataset_name=dataset_name,
        task_type=TaskType.OPEN_QA,
        question=str(record["question"]),
        answer=str(record["expected_answer"]),
        question_id=str(record["case_id"]),
        question_type=question_type,
        history_clips=history_clips,
        haystack_sessions=haystack_sessions,
        haystack_session_ids=haystack_session_ids,
        haystack_session_summaries=haystack_session_summaries,
        haystack_session_datetimes=haystack_session_datetimes,
        gold_evidence=[str(value) for value in record.get("expected_source_ids", [])],
        metadata={
            "task_type": record["task_type"],
            "question_type": question_type,
            "case_type": record["task_type"],
            "generation_template_id": generation_template_id,
            "curated_clips": list(record.get("curated_clips", [])),
            "expected_source_ids": list(record.get("expected_source_ids", [])),
            "stale_source_ids": list(record.get("stale_source_ids", [])),
            "source_ids": [str(session["session_id"]) for session in record["sessions"]],
            "memory_operations": memory_operations,
        },
    )


@register_dataset
class SyntheticWikiMemoryDataset(DatasetAdapter):
    """Dataset adapter for deterministic wiki-style synthetic diagnostics."""

    name = "synthetic-wiki-memory"
    description = "Deterministic synthetic diagnostic dataset for wiki-style memory systems."
    env_override = "WMB_SYNTHETIC_WIKI_MEMORY_SOURCE_FILE"

    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        source_path = self.resolve_source_path()
        examples: list[EvalCase] = []
        with source_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                examples.append(convert_synthetic_case(record, dataset_name=self.name))
                if limit is not None and len(examples) >= limit:
                    break

        return PreparedDataset(
            name=self.name,
            description=self.description,
            examples=examples,
            metadata={"source": str(source_path), "example_count": len(examples)},
        )

    def resolve_source_path(self) -> Path:
        env_path = self._source_path_from_env()
        if env_path:
            return resolve_user_path(env_path)

        default_path = default_synthetic_wiki_memory_path()
        if not default_path.exists():
            export_synthetic_wiki_memory(cases=100, out_path=default_path, seed=42)
        return default_path

    def _source_path_from_env(self) -> str | None:
        import os

        return os.getenv(self.env_override)


def _build_case(task_type: str, case_number: int, rng: random.Random) -> dict[str, Any]:
    person = rng.choice(PEOPLE)
    friend = rng.choice([candidate for candidate in PEOPLE if candidate != person])
    tool_a = rng.choice(TOOLS)
    tool_b = rng.choice([candidate for candidate in TOOLS if candidate != tool_a])
    city_a = rng.choice(CITIES)
    city_b = rng.choice([candidate for candidate in CITIES if candidate != city_a])
    project = rng.choice(PROJECTS)
    hobby = rng.choice(HOBBIES)
    food = rng.choice(FOODS)
    start = datetime(2026, 1, 1, 9, 0) + timedelta(days=case_number * 3)

    if task_type == "direct_recall":
        answer = tool_a
        sessions = [
            _session(
                case_number,
                1,
                start,
                [
                    _message(case_number, 1, 1, person, f"My preferred database for analytics is {answer}."),
                    _message(case_number, 1, 2, friend, f"I'll remember that {answer} is your default."),
                ],
                f"{person} states that {answer} is the preferred database.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=2),
                [
                    _message(case_number, 2, 1, person, f"I also use {tool_b} occasionally for experiments."),
                ],
                f"{person} mentions occasional use of {tool_b}.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"]],
            question=f"Which database should the wiki remember as {person}'s default analytics database?",
            expected_answer=answer,
            expected_source_ids=[sessions[0]["session_id"]],
            memory_operations=["add", "cite"],
        )

    if task_type == "update_latest_fact":
        answer = city_b
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"My office is currently in {city_a}.")],
                f"{person} says the office is in {city_a}.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=5),
                [_message(case_number, 2, 1, person, f"Update the wiki: my office moved from {city_a} to {city_b}.")],
                f"{person} updates the office location to {city_b}.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[1]["messages"][0]["message_id"]],
            question=f"What city should be treated as {person}'s current office location?",
            expected_answer=answer,
            expected_source_ids=[sessions[1]["session_id"]],
            stale_source_ids=[sessions[0]["session_id"]],
            memory_operations=["add", "update", "cite"],
        )

    if task_type == "stale_claim_avoidance":
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"The {project} launch is in May 2026.")],
                f"Initial note says {project} launches in May 2026.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=4),
                [_message(case_number, 2, 1, friend, f"Correction: the {project} launch moved to June 2026; the May note is stale.")],
                f"Correction says {project} launches in June 2026 and the May note is stale.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"], sessions[1]["messages"][0]["message_id"]],
            question=f"Should memory still present the old May 2026 launch plan for {project} as current?",
            expected_answer="No, the old claim is stale. The current launch month is June 2026.",
            expected_source_ids=[sessions[1]["session_id"]],
            stale_source_ids=[sessions[0]["session_id"]],
            memory_operations=["update", "deprecate", "cite"],
        )

    if task_type == "explicit_forgetting":
        answer = "Not enough information in memory."
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"Temporary access code: {case_number:04d}. Do not keep this beyond today.")],
                "A temporary access code is mentioned and marked short-lived.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=1),
                [_message(case_number, 2, 1, friend, "Explicit memory operation: forget the temporary access code after use.")],
                "The temporary access code should be forgotten.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[1]["messages"][0]["message_id"]],
            question="What temporary access code should still be retrievable from long-term memory?",
            expected_answer=answer,
            expected_source_ids=[sessions[1]["session_id"]],
            stale_source_ids=[sessions[0]["session_id"]],
            memory_operations=["add", "forget", "deprecate", "cite"],
        )

    if task_type == "conflicting_sources":
        answer = "4 spaces"
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, "The team style guide says to use tabs for indentation.")],
                "Older style guide claims tabs are required.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=3),
                [_message(case_number, 2, 1, friend, "New style guide: use 4 spaces for indentation from now on.")],
                "Updated style guide says 4 spaces are required.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"], sessions[1]["messages"][0]["message_id"]],
            question="Which indentation rule should be considered authoritative now?",
            expected_answer=answer,
            expected_source_ids=[sessions[1]["session_id"]],
            stale_source_ids=[sessions[0]["session_id"]],
            memory_operations=["update", "deprecate", "cite"],
        )

    if task_type == "multi_source_aggregation":
        answer = f"{project} and {hobby}"
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"This month I started the {project} project.")],
                f"{person} started the {project} project.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=6),
                [_message(case_number, 2, 1, person, f"I also picked up {hobby} on weekends.")],
                f"{person} picked up {hobby} on weekends.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"], sessions[1]["messages"][0]["message_id"]],
            question=f"What two new things should memory combine for {person} this month?",
            expected_answer=answer,
            expected_source_ids=[sessions[0]["session_id"], sessions[1]["session_id"]],
            memory_operations=["add", "cite"],
        )

    if task_type == "temporal_question":
        review_date = (start + timedelta(days=9)).date().isoformat()
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"The design review is on {review_date}.")],
                f"Design review scheduled on {review_date}.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=2),
                [_message(case_number, 2, 1, friend, f"The customer demo is two days after {review_date}.")],
                f"Customer demo happens after {review_date}.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"]],
            question="Which calendar day is reserved for the design review?",
            expected_answer=review_date,
            expected_source_ids=[sessions[0]["session_id"]],
            memory_operations=["add", "cite"],
        )

    if task_type == "citation_required":
        answer = f"{project} launch checklist"
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"I created a note titled '{answer}' in the wiki today.")],
                f"{person} created a note titled {answer}.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=2),
                [_message(case_number, 2, 1, friend, f"Please cite the source page when someone asks about '{answer}'.")],
                f"Team reminder to cite the source page for {answer}.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"], sessions[1]["messages"][0]["message_id"]],
            question="What launch note title should be answered with source support?",
            expected_answer=answer,
            expected_source_ids=[sessions[0]["session_id"]],
            memory_operations=["add", "cite"],
        )

    if task_type == "abstention_when_not_in_memory":
        sessions = [
            _session(
                case_number,
                1,
                start,
                [_message(case_number, 1, 1, person, f"I was working on {project} this week.")],
                f"{person} mentions working on {project}.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=2),
                [_message(case_number, 2, 1, friend, f"{person} still enjoys {hobby}.")],
                f"{person} still enjoys {hobby}.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[],
            question=f"What is {person}'s passport number?",
            expected_answer="Not enough information in memory.",
            expected_source_ids=[],
            memory_operations=["add", "cite"],
        )

    if task_type == "paraphrased_question":
        answer = tool_a
        sessions = [
            _session(
                case_number,
                1,
                start,
                [
                    _message(case_number, 1, 1, person, f"My preferred database for analytics is {answer}."),
                    _message(case_number, 1, 2, friend, f"Noted: {answer} is the analytics datastore to remember."),
                ],
                f"{person}'s analytics datastore preference is {answer}.",
            ),
            _session(
                case_number,
                2,
                start + timedelta(days=2),
                [_message(case_number, 2, 1, person, f"I may compare {tool_b} later, but that is not my default.")],
                f"{person} may evaluate {tool_b}, but it is not the default.",
            ),
        ]
        return _case(
            task_type=task_type,
            case_number=case_number,
            sessions=sessions,
            curated_clips=[sessions[0]["messages"][0]["message_id"]],
            question=f"Which datastore should be treated as {person}'s analytics default, even though the question avoids quoting the original wording?",
            expected_answer=answer,
            expected_source_ids=[sessions[0]["session_id"]],
            memory_operations=["add", "cite"],
        )

    raise ValueError(f"Unsupported synthetic task type: {task_type}")


def _case(
    *,
    task_type: str,
    case_number: int,
    sessions: list[dict[str, Any]],
    curated_clips: list[str],
    question: str,
    expected_answer: str,
    expected_source_ids: list[str],
    memory_operations: list[str],
    stale_source_ids: list[str] | None = None,
) -> dict[str, Any]:
    record = {
        "case_id": f"synthetic-wiki-memory-{task_type}-{case_number:03d}",
        "task_type": task_type,
        "question_type": task_type,
        "generation_template_id": f"{task_type}:v2",
        "sessions": sessions,
        "curated_clips": curated_clips,
        "question": question,
        "expected_answer": expected_answer,
        "expected_source_ids": expected_source_ids,
        "stale_source_ids": stale_source_ids or [],
        "memory_operations": memory_operations,
        "memory_operation_labels": memory_operations,
    }
    validate_synthetic_case(record)
    return record


def validate_synthetic_case(record: dict[str, Any]) -> None:
    """Validate a generated synthetic case for structural consistency."""

    session_ids = {str(session["session_id"]) for session in record["sessions"]}
    message_ids = {
        str(message["message_id"])
        for session in record["sessions"]
        for message in session["messages"]
    }

    expected_source_ids = set(str(value) for value in record.get("expected_source_ids", []))
    stale_source_ids = set(str(value) for value in record.get("stale_source_ids", []))
    curated_clips = [str(value) for value in record.get("curated_clips", [])]
    memory_operations = set(str(value) for value in record.get("memory_operations", record.get("memory_operation_labels", [])))

    if not record.get("task_type"):
        raise ValueError("task_type must not be empty")
    if not record.get("question_type"):
        raise ValueError("question_type must not be empty")
    if not record.get("generation_template_id"):
        raise ValueError("generation_template_id must not be empty")
    if not record.get("expected_answer"):
        raise ValueError("expected_answer must not be empty")
    if not expected_source_ids.issubset(session_ids):
        raise ValueError("all expected_source_ids must exist in sessions")
    if not stale_source_ids.issubset(session_ids):
        raise ValueError("all stale_source_ids must exist in sessions")
    if expected_source_ids & stale_source_ids:
        raise ValueError("expected_source_ids and stale_source_ids must not overlap")
    if any(clip_id not in message_ids for clip_id in curated_clips):
        raise ValueError("all curated_clips must refer to existing messages")
    if record["task_type"] != "abstention_when_not_in_memory" and not curated_clips:
        raise ValueError("curated_clips should be non-empty for non-abstention tasks")
    if not memory_operations.issubset({"add", "update", "deprecate", "forget", "cite"}):
        raise ValueError("memory_operation_labels contains unsupported values")
    if "update" in memory_operations and not expected_source_ids:
        raise ValueError("update tasks should include expected_source_ids")
    if "deprecate" in memory_operations and not stale_source_ids:
        raise ValueError("deprecate tasks should include stale_source_ids")


def _session(case_number: int, session_number: int, timestamp: datetime, messages: list[dict[str, Any]], summary: str) -> dict[str, Any]:
    stamped_messages = [{**message, "timestamp": timestamp.isoformat()} for message in messages]
    return {
        "session_id": f"source-{case_number:03d}-session-{session_number}",
        "timestamp": timestamp.isoformat(),
        "summary": summary,
        "messages": stamped_messages,
    }


def _message(case_number: int, session_number: int, message_number: int, speaker: str, text: str) -> dict[str, Any]:
    return {
        "message_id": f"case-{case_number:03d}-s{session_number}-m{message_number}",
        "speaker": speaker,
        "text": text,
    }
