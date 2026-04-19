"""LongMemEval-cleaned dataset adapters."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

from huggingface_hub import hf_hub_download

from wiki_memory_bench.datasets.base import DatasetAdapter, register_dataset
from wiki_memory_bench.schemas import EvalCase, HistoryClip, PreparedDataset, SessionTurn, TaskType

DATE_PATTERN = re.compile(r"\s+\([A-Za-z]{3}\)")
SPLIT_CONFIGS = {
    "s": {"filename": "longmemeval_s_cleaned.json", "dataset_name": "longmemeval-s", "description": "LongMemEval-cleaned S split."},
    "m": {"filename": "longmemeval_m_cleaned.json", "dataset_name": "longmemeval-m", "description": "LongMemEval-cleaned M split."},
    "oracle": {"filename": "longmemeval_oracle.json", "dataset_name": "longmemeval-oracle", "description": "LongMemEval oracle split."},
}


def parse_longmemeval_datetime(value: str) -> datetime:
    """Parse LongMemEval date strings such as ``2023/05/30 (Tue) 23:40``."""

    cleaned = DATE_PATTERN.sub("", value.strip())
    for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))


def convert_longmemeval_record(record: dict[str, object], dataset_name: str) -> EvalCase:
    """Convert a LongMemEval-cleaned record into the internal eval schema."""

    question_id = str(record["question_id"])
    question_type = str(record["question_type"])
    session_ids = [str(value) for value in record.get("haystack_session_ids", [])]
    session_datetimes = [parse_longmemeval_datetime(str(value)) for value in record.get("haystack_dates", [])]
    raw_sessions = record.get("haystack_sessions", [])
    evidence_session_ids = [str(value) for value in record.get("answer_session_ids", [])]

    haystack_sessions: list[list[SessionTurn]] = []
    history_clips: list[HistoryClip] = []
    evidence_turn_ids: list[str] = []

    for session_index, raw_session in enumerate(raw_sessions):
        session_id = session_ids[session_index] if session_index < len(session_ids) else f"session-{session_index}"
        session_datetime = session_datetimes[session_index] if session_index < len(session_datetimes) else datetime.min
        parsed_turns = [
            SessionTurn(
                role=str(turn["role"]),
                content=str(turn["content"]),
                has_answer=bool(turn.get("has_answer")) if "has_answer" in turn else None,
            )
            for turn in raw_session
        ]
        haystack_sessions.append(parsed_turns)

        for turn_index, turn in enumerate(parsed_turns):
            clip_id = f"{question_id}:{session_id}:turn-{turn_index}"
            history_clips.append(
                HistoryClip(
                    clip_id=clip_id,
                    conversation_id=question_id,
                    session_id=session_id,
                    speaker=turn.role,
                    timestamp=session_datetime,
                    text=turn.content,
                    turn_id=str(turn_index),
                    source_ref=f"{session_id}:turn-{turn_index}",
                    metadata={
                        "question_id": question_id,
                        "question_type": question_type,
                        "has_answer": turn.has_answer,
                    },
                )
            )
            if turn.has_answer:
                evidence_turn_ids.append(clip_id)

    question_date_raw = str(record.get("question_date", ""))
    question_datetime = parse_longmemeval_datetime(question_date_raw) if question_date_raw else None

    return EvalCase(
        example_id=question_id,
        dataset_name=dataset_name,
        task_type=TaskType.OPEN_QA,
        question=str(record["question"]),
        answer=str(record["answer"]),
        history_clips=history_clips,
        question_id=question_id,
        question_type=question_type,
        haystack_sessions=haystack_sessions,
        haystack_session_ids=session_ids,
        haystack_session_datetimes=session_datetimes,
        gold_evidence=evidence_session_ids,
        metadata={
            "source": "xiaowu0162/longmemeval-cleaned",
            "question_type": question_type,
            "question_date": question_date_raw,
            "question_datetime": question_datetime.isoformat() if question_datetime is not None else None,
            "answer_session_ids": evidence_session_ids,
            "evidence_turn_ids": evidence_turn_ids,
            "session_count": len(session_ids),
        },
    )


class _LongMemEvalBaseDataset(DatasetAdapter):
    """Shared implementation for LongMemEval split adapters."""

    repo_id = "xiaowu0162/longmemeval-cleaned"
    split_key = "s"

    def __init__(self, split: str | None = None) -> None:
        resolved_split = split or self.split_key
        if resolved_split not in SPLIT_CONFIGS:
            raise ValueError(f"Unsupported LongMemEval split: {resolved_split}")
        self.split_key = resolved_split
        self.filename = SPLIT_CONFIGS[resolved_split]["filename"]
        self.dataset_name = SPLIT_CONFIGS[resolved_split]["dataset_name"]
        self.description = SPLIT_CONFIGS[resolved_split]["description"]

    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        examples: list[EvalCase] = []
        for index, raw_record in enumerate(self.iter_raw_records()):
            examples.append(convert_longmemeval_record(raw_record, dataset_name=self.dataset_name))
            if limit is not None and index + 1 >= limit:
                break

        return PreparedDataset(
            name=self.dataset_name,
            description=self.description,
            examples=examples,
            metadata={
                "source": f"{self.repo_id}:{self.filename}",
                "split": self.split_key,
                "example_count": len(examples),
                "cached": True,
            },
        )

    def iter_raw_records(self) -> Iterator[dict[str, object]]:
        source_path = self.resolve_source_path()
        with source_path.open(encoding="utf-8") as source_file:
            data = json.load(source_file)
        for record in data:
            yield record

    def resolve_source_path(self) -> Path:
        override = os.getenv("WMB_LONGMEMEVAL_SOURCE_FILE")
        if override:
            return Path(override).expanduser().resolve()

        split_override = os.getenv(f"WMB_LONGMEMEVAL_{self.split_key.upper()}_SOURCE_FILE")
        if split_override:
            return Path(split_override).expanduser().resolve()

        download_path = hf_hub_download(
            repo_id=self.repo_id,
            repo_type="dataset",
            filename=self.filename,
        )
        return Path(download_path)


@register_dataset
class LongMemEvalDataset(_LongMemEvalBaseDataset):
    """Generic LongMemEval dataset entrypoint, defaulting to S split."""

    name = "longmemeval"


@register_dataset
class LongMemEvalSDataset(_LongMemEvalBaseDataset):
    """LongMemEval-cleaned S split."""

    name = "longmemeval-s"
    split_key = "s"


@register_dataset
class LongMemEvalMDataset(_LongMemEvalBaseDataset):
    """LongMemEval-cleaned M split."""

    name = "longmemeval-m"
    split_key = "m"


@register_dataset
class LongMemEvalOracleDataset(_LongMemEvalBaseDataset):
    """LongMemEval oracle split."""

    name = "longmemeval-oracle"
    split_key = "oracle"
