# Synthetic Wiki Memory Dataset

## Why It Exists
Public memory benchmarks are useful, but they usually do not isolate wiki-style maintenance behaviors cleanly.

`synthetic-wiki-memory` exists to test exactly those behaviors in a controlled way:

- what should be added
- what should be updated
- what should be marked stale
- what should be forgotten
- what should be cited

The dataset is intentionally:

- deterministic
- inspectable
- easy to debug
- suitable for regression testing

It is not intended to replace public long-memory datasets. It is intended to complement them.

## Task Types
The current generator emits 10 task families:

1. `direct_recall`
   - Tests whether a system can retrieve a stable fact from memory and cite the supporting session.
2. `update_latest_fact`
   - Tests whether a later update overrides an older fact, with the older session marked stale.
3. `stale_claim_avoidance`
   - Tests whether the system rejects an explicitly stale claim and cites the correction.
4. `explicit_forgetting`
   - Tests whether a temporary fact is no longer answerable after an explicit forget operation.
5. `conflicting_sources`
   - Tests conflict resolution when two sessions disagree and only the later authoritative source should be used.
6. `multi_source_aggregation`
   - Tests whether an answer combines facts from multiple expected source sessions; citation recall and F1 matter here.
7. `temporal_question`
   - Tests date-sensitive recall without requiring the question to repeat the answer wording.
8. `citation_required`
   - Tests whether an answer is grounded in the expected source rather than merely guessed.
9. `abstention_when_not_in_memory`
   - Tests refusal behavior when the requested fact is absent from memory.
10. `paraphrased_question`
    - Tests semantic retrieval when the question avoids the exact wording used in the source session.

## What Each Case Contains
Each generated case includes:

- `task_type`
- `sessions`
- `curated_clips`
- `question`
- `expected_answer`
- `expected_source_ids`
- `stale_source_ids` when relevant
- `memory_operations`
- `memory_operation_labels` for compatibility with older readers
- `question_type`
- `generation_template_id`

The `curated_clips` field is meant to represent what a human would realistically save into a wiki memory layer.

## Generation Templates
The generator uses deterministic templates plus seeded randomness over small pools of:

- people
- tools
- cities
- projects
- hobbies
- foods

This gives:

- stable structure
- varied surface forms
- reproducibility across runs with the same seed

Command:

```bash
uv run wmb synthetic generate --cases 100 --seed 42 --out data/synthetic/wiki_memory_100.jsonl
```

Generation is deterministic: identical `--cases` and `--seed` values produce byte-identical JSONL output. Different seeds change names, tools, cities, projects, hobbies, and foods while preserving the same schema and task rotation.

## Intended Use
Use this dataset for:

- regression testing
- debugging retrieval failures
- comparing curated vs full-memory behaviors
- testing whether a system respects stale and forgetting signals

## Evaluation Guidance

- Use `expected_source_ids` for evidence-aware citation source precision, recall, and F1.
- Use `stale_source_ids` to penalize citations to outdated or explicitly forgotten sources.
- For `multi_source_aggregation`, recall and F1 are more informative than a binary "any expected source cited" check.
- For `explicit_forgetting`, an answer can be correct only if it does not reveal the forgotten temporary value.
- For `abstention_when_not_in_memory`, the expected answer is an abstention phrase and `expected_source_ids` is empty.
- For `paraphrased_question`, a system should retrieve semantically relevant memory rather than depend only on literal answer keywords.

It is especially useful when public datasets do not let you isolate:

- update handling
- deprecation handling
- citation-sensitive behavior

## Limitations
Important limitations:

1. These are synthetic templates, not human-annotated real conversations.
2. A high score here does not imply robust real-world memory performance.
3. Some diagnostic categories are still easier than production maintenance problems.
4. Template text can overfit if systems tune directly to this dataset.
5. Current benchmark metrics are still proxies for long-term memory quality.

## How Not To Overinterpret Results
Do not treat `synthetic-wiki-memory` as:

- a replacement for LoCoMo or LongMemEval
- a standalone leaderboard
- proof that a system is production-ready

Do treat it as:

- a controlled debugging dataset
- a maintenance-behavior stress test
- a regression suite for wiki-style memory systems

## Related Metrics
This dataset is designed to support metrics such as:

- answer accuracy
- update accuracy
- stale claim avoidance
- forgetting compliance
- citation source precision / recall / F1
- stale citation rate
- unsupported answer rate
- patch correctness when available
