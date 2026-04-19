from __future__ import annotations

import json
from pathlib import Path


def build_locomo_record(index: int, question_type: str, question: str, answer: str) -> dict[str, object]:
    session_ids = ["session_1", "session_2"]
    session_datetimes = ["2023-05-08T13:56:00", "2023-05-25T13:14:00"]
    session_summaries = [
        f"Session 1 summary for case {index}: background details.",
        f"Session 2 summary for case {index}: the correct answer is {answer}.",
    ]
    sessions = [
        [
            {"role": "user", "content": f"Question context for case {index}."},
            {"role": "assistant", "content": f"Earlier distractor detail for case {index}."},
        ],
        [
            {"role": "user", "content": f"Latest update for case {index}."},
            {"role": "assistant", "content": f"The correct answer for case {index} is {answer}."},
        ],
    ]
    choices = [
        answer,
        f"wrong-{index}-1",
        f"wrong-{index}-2",
        f"wrong-{index}-3",
        f"wrong-{index}-4",
        f"wrong-{index}-5",
        f"wrong-{index}-6",
        f"wrong-{index}-7",
        f"wrong-{index}-8",
        "Not answerable",
    ]
    return {
        "question_id": f"conv-{index}_q{index}",
        "question_type": question_type,
        "question": question,
        "choices": choices,
        "correct_choice_index": 0,
        "answer": answer,
        "haystack_sessions": sessions,
        "haystack_session_ids": session_ids,
        "haystack_session_summaries": session_summaries,
        "haystack_session_datetimes": session_datetimes,
        "num_choices": len(choices),
        "num_sessions": len(session_ids),
    }


def write_locomo_fixture(path: Path) -> Path:
    records = [
        build_locomo_record(1, "single_hop", "Which project codename is active?", "Aurora"),
        build_locomo_record(2, "multi_hop", "Which city is the current office in?", "Seattle"),
        build_locomo_record(3, "temporal_reasoning", "When is the architecture review?", "2026-04-21"),
        build_locomo_record(4, "open_domain", "Which database is preferred?", "PostgreSQL"),
        build_locomo_record(5, "adversarial", "What is the final published plan name?", "Northstar"),
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path
