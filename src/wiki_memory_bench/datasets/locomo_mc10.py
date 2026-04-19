"""LoCoMo-MC10 dataset adapter backed by Hugging Face local cache."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator

from huggingface_hub import hf_hub_download

from wiki_memory_bench.datasets.base import DatasetAdapter, register_dataset
from wiki_memory_bench.schemas import ChoiceOption, EvalCase, HistoryClip, PreparedDataset, SessionTurn, TaskType

CHOICE_LABELS = list("ABCDEFGHIJ")


def parse_datetime(value: str) -> datetime:
    """Parse ISO-like datetime strings from the dataset."""

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def build_choice_options(choices: list[str]) -> list[ChoiceOption]:
    """Convert raw choice strings into normalized option models."""

    return [
        ChoiceOption(choice_id=f"choice-{index + 1}", label=CHOICE_LABELS[index], text=choice_text)
        for index, choice_text in enumerate(choices)
    ]


def convert_locomo_record(record: dict[str, object], dataset_name: str = "locomo-mc10") -> EvalCase:
    """Convert a LoCoMo-MC10 raw record into the internal eval schema."""

    question_id = str(record["question_id"])
    conversation_id = question_id.rsplit("_q", 1)[0]
    question_type = str(record["question_type"])
    session_ids = [str(value) for value in record["haystack_session_ids"]]
    session_summaries = [str(value) for value in record["haystack_session_summaries"]]
    session_datetimes = [parse_datetime(str(value)) for value in record["haystack_session_datetimes"]]
    raw_sessions = record["haystack_sessions"]

    haystack_sessions: list[list[SessionTurn]] = []
    history_clips: list[HistoryClip] = []

    for session_index, raw_session in enumerate(raw_sessions):
        session_id = session_ids[session_index]
        session_datetime = session_datetimes[session_index]
        parsed_turns = [
            SessionTurn(role=str(turn["role"]), content=str(turn["content"]))
            for turn in raw_session
        ]
        haystack_sessions.append(parsed_turns)

        for turn_index, turn in enumerate(parsed_turns):
            history_clips.append(
                HistoryClip(
                    clip_id=f"{question_id}:{session_id}:turn-{turn_index}",
                    conversation_id=conversation_id,
                    session_id=session_id,
                    speaker=turn.role,
                    timestamp=session_datetime,
                    text=turn.content,
                    turn_id=str(turn_index),
                    source_ref=f"{session_id}:turn-{turn_index}",
                    metadata={"question_id": question_id, "question_type": question_type},
                )
            )

    correct_choice_index = int(record["correct_choice_index"])
    choices = build_choice_options([str(choice) for choice in record["choices"]])

    return EvalCase(
        example_id=question_id,
        dataset_name=dataset_name,
        task_type=TaskType.MULTIPLE_CHOICE,
        question=str(record["question"]),
        choices=choices,
        history_clips=history_clips,
        correct_choice_index=correct_choice_index,
        question_id=question_id,
        question_type=question_type,
        answer=str(record["answer"]),
        haystack_sessions=haystack_sessions,
        haystack_session_ids=session_ids,
        haystack_session_summaries=session_summaries,
        haystack_session_datetimes=session_datetimes,
        metadata={
            "source": "Percena/locomo-mc10",
            "question_type": question_type,
            "num_choices": int(record.get("num_choices", len(choices))),
            "num_sessions": int(record.get("num_sessions", len(session_ids))),
        },
    )


@register_dataset
class LoCoMoMc10Dataset(DatasetAdapter):
    """LoCoMo-MC10 multiple-choice dataset."""

    name = "locomo-mc10"
    description = "LoCoMo-MC10 multiple-choice benchmark from Percena/locomo-mc10."
    repo_id = "Percena/locomo-mc10"
    filename = "data/locomo_mc10.json"
    env_override = "WMB_LOCOMO_MC10_SOURCE_FILE"

    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        examples: list[EvalCase] = []
        for index, raw_record in enumerate(self.iter_raw_records()):
            examples.append(convert_locomo_record(raw_record, dataset_name=self.name))
            if limit is not None and index + 1 >= limit:
                break

        return PreparedDataset(
            name=self.name,
            description=self.description,
            examples=examples,
            metadata={
                "source": f"{self.repo_id}:{self.filename}",
                "example_count": len(examples),
                "cached": True,
            },
        )

    def iter_raw_records(self) -> Iterator[dict[str, object]]:
        """Yield parsed jsonl-like records from the dataset source file."""

        source_path = self.resolve_source_path()
        with source_path.open(encoding="utf-8") as source_file:
            for line in source_file:
                if line.strip():
                    yield json.loads(line)

    def resolve_source_path(self) -> Path:
        """Resolve the cached or overridden dataset source path."""

        override = os.getenv(self.env_override)
        if override:
            return Path(override).expanduser().resolve()

        download_path = hf_hub_download(
            repo_id=self.repo_id,
            repo_type="dataset",
            filename=self.filename,
        )
        return Path(download_path)
