# Testing and verification

This guide separates the automated baseline from manual checks that can be repeated after changes.

## Automated tests

Run from the repository root in CMD:

```bat
python -m pytest -q
```

The recorded development baseline was **25 passed**. Rerun the suite on the current checkout before release; this historical result is not a guarantee about a later code/dependency state.

Focused retrieval tests:

```bat
python -m pytest tests\test_retrieval.py -q
```

## Test areas

| Area | Test file | Focus |
|---|---|---|
| Retrieval | `tests/test_retrieval.py` | Retrieval/ranking behaviour covered by its assertions. |
| Source catalogue | `tests/test_source_catalogue.py` | Catalogue parsing and normalization cases covered by its assertions. |
| UI flow | `tests/test_ui_flow.py` | AppTest rendering, stable keys, send/clear, prompts, guardrail, and error paths using mocks. |
| Voice | `tests/test_voice.py` | Voice transcription behaviour using mocks. |
| Year filter | `tests/test_year_filter_patch.py` | Fiscal-year-aware retrieval cases covered by its assertions. |
| Fixtures | `tests/conftest.py` | Shared pytest setup. |

Use the test code as the authoritative description of each assertion.

## Manual smoke tests

Mark each row only after running it on the current build.

| ID | Check | Expected observation | Result |
|---|---|---|---|
| M-01 | Launch with `streamlit run app.py` | Home page loads. | Pending |
| M-02 | Ask about an indexed PDF | Answer and source information appear. | Pending |
| M-03 | Expand source details | Excerpt and metadata can be inspected. | Pending |
| M-04 | Ask about an unindexed topic | App communicates that evidence is insufficient/not found. | Pending |
| M-05 | Submit empty input if UI permits | Empty question is rejected. | Pending |
| M-06 | Try a harmless string matching a known injection pattern | Guardrail blocks it before retrieval. | Pending |
| M-07 | Record a voice question | Editable transcript appears before Send. | Pending |
| M-08 | Ingest a trusted PDF | Outcome is reported and source is registered. | Pending |
| M-09 | Re-ingest identical content | Duplicate detection is reported. | Pending |
| M-10 | Ingest a trusted HTML/PDF URL | Extraction and ingestion outcome are reported. | Pending |
| M-11 | Refresh GO catalogue and select one URL | Records can be reviewed; selected documents are sent for ingestion. | Pending |
| M-12 | Compare Vector, BM25, Hybrid | Evidence can be compared for relevance. | Pending |
| M-13 | Ask a question with an indexed fiscal year | Returned evidence is checked for the intended year. | Pending |
| M-14 | Export source registry | CSV is produced. | Pending |
| M-15 | Clear chat | Current session's visible history clears. | Pending |

Pending means not yet verified in this checklist; it is not a claim that the check has passed.

## Retrieval evaluation protocol
1. Record the exact question and expected source.
2. Run all three retrieval modes on the same corpus.
3. Capture top passages, source titles, and page numbers.
4. Judge whether the passage directly supports the requested fact.
5. Check that the answer references relevant evidence.
6. Investigate mismatches before changing chunking or retrieval logic.

Useful measures include expected-source presence in top-k results, passage sufficiency, year constraint adherence, and traceability of factual claims.

## Run record

| Date | Environment | Command | Result | Notes |
|---|---|---|---|---|
| Development baseline | Python 3.12 environment | `python -m pytest -q` | 25 passed (recorded) | Rerun on current checkout. |
| Fill in | Fill in | Fill in | Fill in | Fill in |
