# ClipWiki Failure Analysis

## Initial Failure Pattern

Before the deterministic ClipWiki fixes, the synthetic wiki-memory run was failing in a few repeatable ways:

- concept pages copied the raw `Question:` text into page content, so retrieval could rank navigation pages above actual evidence
- deterministic open-QA extraction treated metadata lines like `Question:` and `Summary:` as answer candidates
- speaker extraction only handled bracketed uppercase names reliably, which weakened people-page linking and evidence organization
- retrieval scored all page types equally, so `concept`, `index`, and `log` pages could displace source-bearing pages

These issues compounded on `synthetic-wiki-memory`, where the previous deterministic `clipwiki` result was about `10.00%` accuracy and `10.00%` citation precision on 50 cases.

## Fixes Applied

### Compiler and page model

- added `page_type`, `is_answerable`, `search_text`, and `timestamp` metadata to the in-memory page model
- introduced explicit `evidence/` pages with clean evidence snippets per session
- updated source pages to surface clean evidence snippets before transcript text
- removed raw question text from concept page searchable body content
- kept concept, index, and log pages as navigation-only by default
- made curated mode use `curated_clips` when they are available for snippet selection

### Retrieval

- switched ClipWiki retrieval to rank on clean `search_text` instead of raw page bodies alone
- added page-type biases so `evidence`, `source`, and `preference` pages outrank `concept`, `index`, and `log`
- added a small recency bonus for dated evidence-bearing pages, which helps update and contradiction tasks

### Deterministic answer extraction

- filtered metadata-prefixed lines from open-QA candidate extraction
- preferred answer-bearing source/evidence snippets over navigation text
- added abstention handling for missing evidence and forgetting-style snippets
- added simple multi-snippet combination for aggregation-style questions

### Speaker extraction

- added support for `**Morgan**: ...`
- added support for `Morgan: ...`
- kept support for `[MORGAN] ...`

## Validation

Targeted regression tests added:

- `test_concept_pages_do_not_include_raw_question`
- `test_answerer_ignores_question_metadata_lines`
- `test_clipwiki_retrieval_prefers_source_pages`
- `test_speaker_extraction_supports_bold_markdown_names`
- `test_clipwiki_synthetic_threshold_20_cases`

Measured after the fixes:

- `clipwiki` on deterministic `synthetic-wiki-memory` 50 cases: `70.00%` accuracy, `60.00%` citation precision
- `bm25` on the same 50-case file: `70.00%` accuracy, `50.00%` citation precision

The synthetic regression threshold now passes comfortably, and direct-recall test coverage enforces retrieval of at least one `source` or `evidence` page.

## Remaining Limitations

- multi-page synthesis is still heuristic and can miss some paraphrased or compositional answers
- `person` and `event` pages are useful for navigation but are intentionally not treated as primary answer evidence
- retrieval is still lexical, so future gains will likely come from better snippet ranking or deterministic aggregation logic rather than more wiki page types
