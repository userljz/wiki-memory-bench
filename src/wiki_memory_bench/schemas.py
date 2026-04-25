"""Shared Pydantic schemas for the benchmark runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskType(str, Enum):
    """Supported task families for the current skeleton."""

    MULTIPLE_CHOICE = "multiple-choice"
    OPEN_QA = "open-qa"


class SessionTurn(BaseModel):
    """Single turn in a haystack session."""

    model_config = ConfigDict(extra="forbid")

    role: str
    content: str
    has_answer: bool | None = None


class HistoryClip(BaseModel):
    """Atomic memory input unit used by datasets and systems."""

    model_config = ConfigDict(extra="forbid")

    clip_id: str
    conversation_id: str
    session_id: str
    speaker: str
    timestamp: datetime
    text: str
    turn_id: str | None = None
    source_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChoiceOption(BaseModel):
    """Single multiple-choice option."""

    model_config = ConfigDict(extra="forbid")

    choice_id: str
    label: str
    text: str


class EvalCase(BaseModel):
    """Normalized evaluation case shared across datasets."""

    model_config = ConfigDict(extra="forbid")

    example_id: str
    dataset_name: str
    task_type: TaskType
    question: str
    choices: list[ChoiceOption] = Field(default_factory=list)
    history_clips: list[HistoryClip] = Field(default_factory=list)
    correct_choice_id: str | None = None
    correct_choice_index: int | None = None
    question_id: str | None = None
    question_type: str | None = None
    answer: str | None = None
    haystack_sessions: list[list[SessionTurn]] = Field(default_factory=list)
    haystack_session_ids: list[str] = Field(default_factory=list)
    haystack_session_summaries: list[str] = Field(default_factory=list)
    haystack_session_datetimes: list[datetime] = Field(default_factory=list)
    gold_evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_multiple_choice_fields(self) -> "EvalCase":
        if self.question_id is None:
            self.question_id = self.example_id
        if self.question_type is None:
            self.question_type = str(self.metadata.get("question_type", "unknown"))

        if self.task_type == TaskType.OPEN_QA:
            if not self.answer:
                raise ValueError("answer must be provided for open-qa tasks")
            return self

        if not self.choices:
            raise ValueError("choices must not be empty")

        choice_ids = [choice.choice_id for choice in self.choices]

        if self.correct_choice_index is None:
            if self.correct_choice_id is None:
                raise ValueError("either correct_choice_index or correct_choice_id must be provided")
            try:
                self.correct_choice_index = choice_ids.index(self.correct_choice_id)
            except ValueError as error:
                raise ValueError("correct_choice_id must match one of the available choices") from error

        if self.correct_choice_index < 0 or self.correct_choice_index >= len(self.choices):
            raise ValueError("correct_choice_index is out of range")

        if self.correct_choice_id is None:
            self.correct_choice_id = self.choices[self.correct_choice_index].choice_id

        if self.answer is None:
            self.answer = self.choices[self.correct_choice_index].text

        return self


PreparedExample = EvalCase


class PreparedDataset(BaseModel):
    """In-memory dataset returned by a dataset adapter."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    examples: list[EvalCase]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """Grounding reference emitted by a system."""

    model_config = ConfigDict(extra="forbid")

    clip_id: str
    source_ref: str | None = None
    quote: str | None = None


class RetrievedItem(BaseModel):
    """Debug view of retrieved context used by a system."""

    model_config = ConfigDict(extra="forbid")

    clip_id: str
    rank: int
    score: float
    text: str
    retrieved_tokens: int = 0


class TokenUsage(BaseModel):
    """Deterministic token estimate for a prediction."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    @model_validator(mode="after")
    def sync_total(self) -> "TokenUsage":
        self.total_tokens = self.input_tokens + self.output_tokens
        return self


class SystemResult(BaseModel):
    """Single system prediction before metric scoring."""

    model_config = ConfigDict(extra="forbid")

    example_id: str
    system_name: str
    selected_choice_id: str | None = None
    selected_choice_index: int | None = None
    selected_choice_text: str | None = None
    answer_text: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    retrieved_items: list[RetrievedItem] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    citation_precision: float | None = None
    wiki_size_pages: int | None = None
    wiki_size_tokens: int | None = None
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluatedExampleResult(BaseModel):
    """Prediction plus deterministic scoring output."""

    model_config = ConfigDict(extra="forbid")

    example_id: str
    question_id: str
    question_type: str
    system_name: str
    status: str = "ok"
    error_type: str | None = None
    error_message: str | None = None
    traceback_path: str | None = None
    selected_choice_id: str | None = None
    selected_choice_index: int | None = None
    selected_choice_text: str | None = None
    answer_text: str | None = None
    correct_choice_id: str
    correct_choice_index: int
    is_correct: bool
    citations: list[Citation] = Field(default_factory=list)
    retrieved_items: list[RetrievedItem] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    citation_precision: float | None = None
    wiki_size_pages: int | None = None
    wiki_size_tokens: int | None = None
    retrieved_token_count: int = 0
    retrieved_chunk_count: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunManifest(BaseModel):
    """Top-level metadata for a benchmark run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    dataset_name: str
    system_name: str
    started_at: datetime
    completed_at: datetime
    run_dir: str
    example_count: int
    limit: int | None = None
    sample: int | None = None
    seed: int = 42
    run_name: str | None = None
    system_options: dict[str, Any] = Field(default_factory=dict)
    answerer: str = "deterministic"
    judge: str = "deterministic"
    dataset_metadata: dict[str, Any] = Field(default_factory=dict)
    package_version: str | None = None
    python_version: str | None = None
    cli_version: str | None = None
    continue_on_error: bool = False
    fail_fast: bool = True
    error_policy: str = "fail_fast"
    dependency_versions: dict[str, str | None] = Field(default_factory=dict)
    platform: dict[str, str] = Field(default_factory=dict)
    extras_enabled: list[str] = Field(default_factory=list)
    git_commit: str | None = None
    git_dirty: bool | None = None
    git_status: str | None = None
    command: str | None = None


class RunSummary(BaseModel):
    """Aggregated run metrics used by report rendering."""

    model_config = ConfigDict(extra="forbid")

    dataset_name: str
    system_name: str
    example_count: int
    completed_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    correct_count: int
    accuracy: float
    accuracy_by_question_type: dict[str, float] = Field(default_factory=dict)
    avg_latency_ms: float
    total_latency_ms: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_total_tokens: float
    total_tokens: int
    avg_estimated_cost_usd: float = 0.0
    total_estimated_cost_usd: float = 0.0
    citation_precision: float | None = None
    citation_source_precision: float | None = None
    citation_source_recall: float | None = None
    citation_source_f1: float | None = None
    stale_citation_rate: float = 0.0
    answer_correct_but_bad_citation_rate: float = 0.0
    unsupported_answer_rate: float = 0.0
    diagnostic_metrics: dict[str, float] = Field(default_factory=dict)
    avg_wiki_size_pages: float = 0.0
    avg_wiki_size_tokens: float = 0.0
    retrieval_top_k: int | None = None
    avg_retrieved_chunk_count: float = 0.0
    total_retrieved_chunk_count: int = 0
    avg_retrieved_tokens: float = 0.0
    total_retrieved_tokens: int = 0
    oracle_label: str = "non-oracle"
    uses_gold_labels: bool = False
    oracle_mode: bool = False
