from pathlib import Path

from wiki_memory_bench.datasets import get_dataset
from wiki_memory_bench.datasets.locomo_mc10 import convert_locomo_record
from tests.locomo_fixture import build_locomo_record, write_locomo_fixture


def test_convert_locomo_record_preserves_required_fields() -> None:
    record = build_locomo_record(1, "single_hop", "Which project codename is active?", "Aurora")
    case = convert_locomo_record(record)

    assert case.question_id == "conv-1_q1"
    assert case.question_type == "single_hop"
    assert case.question == "Which project codename is active?"
    assert len(case.choices) == 10
    assert case.correct_choice_index == 0
    assert case.answer == "Aurora"
    assert case.haystack_session_ids == ["session_1", "session_2"]
    assert len(case.haystack_session_summaries) == 2
    assert len(case.haystack_session_datetimes) == 2
    assert len(case.haystack_sessions) == 2
    assert len(case.history_clips) == 4


def test_locomo_dataset_loads_first_five_examples_from_fixture(tmp_path: Path, monkeypatch) -> None:
    fixture_path = write_locomo_fixture(tmp_path / "locomo_mc10.json")
    monkeypatch.setenv("WMB_LOCOMO_MC10_SOURCE_FILE", str(fixture_path))

    dataset = get_dataset("locomo-mc10").load(limit=5)
    assert dataset.name == "locomo-mc10"
    assert len(dataset.examples) == 5
    assert dataset.examples[0].question_id == "conv-1_q1"
    assert dataset.examples[-1].question_type == "adversarial"
