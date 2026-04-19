"""Optional LLM judge implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wiki_memory_bench.schemas import TokenUsage
from wiki_memory_bench.utils.llm import LiteLLMRuntime


class LLMJudge:
    """LLM-based answer correctness judge."""

    def __init__(self, task_name: str = "judge") -> None:
        self.runtime = LiteLLMRuntime(task_name=task_name)

    def set_artifact_dir(self, artifact_dir: Path) -> None:
        """Attach a run-local artifact directory for prompt logs."""

        self.runtime.set_artifact_dir(artifact_dir)

    def judge_answer(
        self,
        *,
        question: str,
        gold_answer: str,
        predicted_answer: str,
    ) -> tuple[dict[str, Any], TokenUsage, dict[str, Any]]:
        """Compare a predicted answer with the gold answer using an LLM."""

        prompt = "\n".join(
            [
                "You are a benchmark judge.",
                "Compare the predicted answer against the gold answer.",
                "Return ONLY a JSON object with this schema:",
                '{"score": 0 or 1, "reason": str, "matched_facts": [str], "missing_facts": [str]}',
                "",
                f"Question: {question}",
                f"Gold answer: {gold_answer}",
                f"Predicted answer: {predicted_answer}",
                "",
                "Score 1 means the predicted answer correctly matches the gold answer.",
                "Score 0 means it is incorrect or missing essential facts.",
            ]
        )
        return self.runtime.complete_json(prompt)
