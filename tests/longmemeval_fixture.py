from __future__ import annotations

import json
from pathlib import Path


def build_longmemeval_record(index: int, question_type: str, question: str, answer: str) -> dict[str, object]:
    session_ids = [f"session_{index}_1", f"session_{index}_2"]
    haystack_dates = ["2023/05/20 (Sat) 02:21", "2023/05/20 (Sat) 03:21"]
    sessions = [
        [
            {"role": "user", "content": f"General context for case {index}."},
            {"role": "assistant", "content": f"Earlier distractor for case {index}."},
        ],
        [
            {"role": "user", "content": f"Reminder for case {index}."},
            {"role": "assistant", "content": f"The answer for case {index} is {answer}.", "has_answer": True},
        ],
    ]
    return {
        "question_id": f"lm-{index}",
        "question_type": question_type,
        "question": question,
        "answer": answer,
        "question_date": "2023/05/30 (Tue) 23:40",
        "haystack_session_ids": session_ids,
        "haystack_dates": haystack_dates,
        "haystack_sessions": sessions,
        "answer_session_ids": [session_ids[-1]],
    }


def write_longmemeval_fixture(path: Path) -> Path:
    records = [
        build_longmemeval_record(1, "single-session-user", "What degree did I graduate with?", "Business Administration"),
        build_longmemeval_record(2, "temporal-reasoning", "When did I move to Seattle?", "2023/05/20"),
    ]
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return path
