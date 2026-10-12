# Retrieval strategy

The app exposes Vector, BM25, and Hybrid modes so retrieval evidence can be compared against the same indexed corpus.

## Vector retrieval
Uses embedding similarity to retrieve semantically related chunks. It can find conceptually related wording even when a question and source do not share exact terms.

**Inspect:** whether the passage contains the specific scheme, condition, year, or fact requested. Similarity is a relevance signal, not proof that a passage answers the question.

## BM25 retrieval
Uses token-level matching and ranking. The implementation uses Unicode-aware tokenization, including Tamil characters, and has a lexical-overlap fallback if the BM25 package is unavailable.

**Inspect:** exact term matches and whether the passage answers the question rather than merely repeating a keyword.

## Hybrid and Reciprocal Rank Fusion
Hybrid retrieval combines ranked lists using Reciprocal Rank Fusion (RRF). A common RRF scoring form is:

\\[
\\operatorname{RRF}(d) = \\sum_{r \\in R(d)} \\frac{1}{k + \\operatorname{rank}_r(d)}
\\]

The implementation's default smoothing constant is 60. Duplicate chunks are deduplicated using available chunk/source/page/content identifiers.

Hybrid is a strategy to compare, not a guarantee that every query will improve.

## Tamil query expansion
Selected Tamil agriculture-service questions receive targeted English query variants while the original question is retained. This can help when the source uses English terms for a service or benefit.

## Fiscal-year-aware retrieval
Explicit fiscal-year expressions can trigger source filtering based on source metadata such as title, URL, or name. If vector retrieval returns no matching result for an explicit year, a BM25 fallback path is available. This depends on the year being represented in metadata.

## Why semantic similarity can miss a passage
A relevant-looking chunk may omit the exact number, year, eligibility clause, or scheme wording. A long rule may be split across chunks, and retrieval cannot find material that was never ingested.

Diagnostic sequence:
1. Confirm the source is indexed.
2. Compare Vector and BM25 for the same question.
3. Try Hybrid and inspect passages.
4. Make the question more specific.
5. Review chunk boundaries and metadata if needed.
6. Verify against the original source.

## Comparison worksheet

| Test ID | Question | Expected source | Vector top result | BM25 top result | Hybrid top result | Evidence adequate? |
|---|---|---|---|---|---|---|
| R-01 | Exact scheme name | Fill in | Record | Record | Record | Yes / No |
| R-02 | Tamil question, English source terminology | Fill in | Record | Record | Record | Yes / No |
| R-03 | Explicit financial year | Fill in | Record | Record | Record | Yes / No |
| R-04 | Exact benefit or eligibility phrase | Fill in | Record | Record | Record | Yes / No |

Record actual results. Compare multiple representative questions rather than judging a retrieval mode from one example.
