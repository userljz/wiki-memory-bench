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
2. `knowledge_update`
3. `stale_claim_detection`
4. `temporal_reasoning`
5. `contradiction_resolution`
6. `selective_forgetting`
7. `citation_required`
8. `preference_following`
9. `multi_session_aggregation`
10. `abstention`

## What Each Case Contains
Each generated case includes:

- `task_type`
- `sessions`
- `curated_clips`
- `question`
- `expected_answer`
- `expected_source_ids`
- `stale_source_ids` when relevant
- `memory_operation_labels`

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
uv run wmb synthetic generate --cases 100 --out data/synthetic/wiki_memory_100.jsonl
```

## Intended Use
Use this dataset for:

- regression testing
- debugging retrieval failures
- comparing curated vs full-memory behaviors
- testing whether a system respects stale and forgetting signals

It is especially useful when public datasets do not let you isolate:

- update handling
- deprecation handling
- citation-sensitive behavior

## Limitations
Important limitations:

1. These are synthetic templates, not human-annotated real conversations.
2. A high score here does not imply robust real-world memory performance.
3. Some diagnostic categories are still easier than production maintenance problems.
4. Current benchmark metrics are only proxies for long-term memory quality.

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
- citation precision
- source coverage
- patch correctness when available
