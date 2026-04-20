from wiki_memory_bench.metrics.exact import compute_open_qa_match


def test_open_qa_match_does_not_use_raw_substring_false_positive() -> None:
    exact, partial = compute_open_qa_match("yesterday", "yes")
    assert exact is False
    assert partial is False


def test_open_qa_match_allows_token_superset_partial_match() -> None:
    exact, partial = compute_open_qa_match("Business Administration degree", "Business Administration")
    assert exact is False
    assert partial is True
