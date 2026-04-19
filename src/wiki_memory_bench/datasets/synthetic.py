"""Built-in synthetic starter dataset."""

from __future__ import annotations

from datetime import datetime

from wiki_memory_bench.datasets.base import DatasetAdapter, register_dataset
from wiki_memory_bench.schemas import ChoiceOption, HistoryClip, PreparedDataset, PreparedExample, TaskType


def _clip(
    clip_id: str,
    conversation_id: str,
    session_id: str,
    speaker: str,
    timestamp: str,
    text: str,
) -> HistoryClip:
    return HistoryClip(
        clip_id=clip_id,
        conversation_id=conversation_id,
        session_id=session_id,
        speaker=speaker,
        timestamp=datetime.fromisoformat(timestamp),
        text=text,
        source_ref=f"synthetic://{conversation_id}/{clip_id}",
    )


def _choices(*values: str) -> list[ChoiceOption]:
    labels = ["A", "B", "C", "D", "E"]
    return [
        ChoiceOption(choice_id=f"choice-{index + 1}", label=labels[index], text=value)
        for index, value in enumerate(values)
    ]


@register_dataset
class SyntheticMiniDataset(DatasetAdapter):
    """Five deterministic starter cases for the benchmark skeleton."""

    name = "synthetic-mini"
    description = "Tiny built-in dataset with recall, update, temporal, contradiction, and abstention cases."

    def load(self, limit: int | None = None, sample: int | None = None) -> PreparedDataset:
        examples = [
            PreparedExample(
                example_id="synthetic-mini-direct-recall",
                dataset_name=self.name,
                task_type=TaskType.MULTIPLE_CHOICE,
                question="Which database is Avery's favorite for analytics work?",
                history_clips=[
                    _clip(
                        "clip-1",
                        "conv-direct-recall",
                        "session-1",
                        "avery",
                        "2026-04-01T09:00:00",
                        "My favorite database for analytics work is PostgreSQL.",
                    ),
                ],
                choices=_choices(
                    "PostgreSQL",
                    "Redis",
                    "SQLite",
                    "Not enough information in memory",
                ),
                correct_choice_index=0,
                question_id="synthetic-mini-direct-recall",
                question_type="direct_recall",
                answer="PostgreSQL",
                correct_choice_id="choice-1",
                gold_evidence=["clip-1"],
                metadata={"case_type": "direct_recall", "question_type": "direct_recall"},
            ),
            PreparedExample(
                example_id="synthetic-mini-updated-fact",
                dataset_name=self.name,
                task_type=TaskType.MULTIPLE_CHOICE,
                question="Where is Avery's current office?",
                history_clips=[
                    _clip(
                        "clip-2",
                        "conv-updated-fact",
                        "session-1",
                        "avery",
                        "2026-01-10T09:00:00",
                        "At the start of the year, my office was in Austin.",
                    ),
                    _clip(
                        "clip-3",
                        "conv-updated-fact",
                        "session-2",
                        "avery",
                        "2026-03-15T18:00:00",
                        "Update for the team wiki: my office is now in Seattle.",
                    ),
                ],
                choices=_choices(
                    "Austin",
                    "Seattle",
                    "Denver",
                    "Not enough information in memory",
                ),
                correct_choice_index=1,
                question_id="synthetic-mini-updated-fact",
                question_type="updated_fact",
                answer="Seattle",
                correct_choice_id="choice-2",
                gold_evidence=["clip-3"],
                metadata={"case_type": "updated_fact", "question_type": "updated_fact"},
            ),
            PreparedExample(
                example_id="synthetic-mini-temporal",
                dataset_name=self.name,
                task_type=TaskType.MULTIPLE_CHOICE,
                question="On what date is the architecture review scheduled?",
                history_clips=[
                    _clip(
                        "clip-4",
                        "conv-temporal",
                        "session-1",
                        "program-manager",
                        "2026-04-05T10:30:00",
                        "The architecture review is scheduled for 2026-04-21.",
                    ),
                    _clip(
                        "clip-5",
                        "conv-temporal",
                        "session-1",
                        "program-manager",
                        "2026-04-05T10:35:00",
                        "The customer demo is scheduled for 2026-04-25.",
                    ),
                ],
                choices=_choices(
                    "2026-04-19",
                    "2026-04-21",
                    "2026-04-25",
                    "Not enough information in memory",
                ),
                correct_choice_index=1,
                question_id="synthetic-mini-temporal",
                question_type="temporal_question",
                answer="2026-04-21",
                correct_choice_id="choice-2",
                gold_evidence=["clip-4"],
                metadata={"case_type": "temporal_question", "question_type": "temporal_question"},
            ),
            PreparedExample(
                example_id="synthetic-mini-contradiction",
                dataset_name=self.name,
                task_type=TaskType.MULTIPLE_CHOICE,
                question="What indentation style should the repo use now?",
                history_clips=[
                    _clip(
                        "clip-6",
                        "conv-contradiction",
                        "session-1",
                        "maintainer",
                        "2026-02-01T08:00:00",
                        "Old style note: use tabs for indentation in this repo.",
                    ),
                    _clip(
                        "clip-7",
                        "conv-contradiction",
                        "session-2",
                        "maintainer",
                        "2026-04-02T12:00:00",
                        "Correction: use 4 spaces for indentation in this repo from now on.",
                    ),
                ],
                choices=_choices(
                    "tabs",
                    "2 spaces",
                    "4 spaces",
                    "Not enough information in memory",
                ),
                correct_choice_index=2,
                question_id="synthetic-mini-contradiction",
                question_type="contradiction",
                answer="4 spaces",
                correct_choice_id="choice-3",
                gold_evidence=["clip-7"],
                metadata={"case_type": "contradiction", "question_type": "contradiction"},
            ),
            PreparedExample(
                example_id="synthetic-mini-abstention",
                dataset_name=self.name,
                task_type=TaskType.MULTIPLE_CHOICE,
                question="Which cloud region hosts the staging environment?",
                history_clips=[
                    _clip(
                        "clip-8",
                        "conv-abstention",
                        "session-1",
                        "devops",
                        "2026-04-03T11:00:00",
                        "The staging environment uses PostgreSQL 16.",
                    ),
                    _clip(
                        "clip-9",
                        "conv-abstention",
                        "session-1",
                        "devops",
                        "2026-04-03T11:05:00",
                        "The API service runs in a container on our internal cluster.",
                    ),
                ],
                choices=_choices(
                    "us-west-2",
                    "eu-west-1",
                    "ap-southeast-1",
                    "Not enough information in memory",
                ),
                correct_choice_index=3,
                question_id="synthetic-mini-abstention",
                question_type="abstention",
                answer="Not enough information in memory",
                correct_choice_id="choice-4",
                gold_evidence=[],
                metadata={"case_type": "abstention", "question_type": "abstention"},
            ),
        ]

        if limit is not None:
            examples = examples[:limit]

        return PreparedDataset(
            name=self.name,
            description=self.description,
            examples=examples,
            metadata={"built_in": True, "example_count": len(examples)},
        )
