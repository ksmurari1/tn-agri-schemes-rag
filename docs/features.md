# Feature guide

## Home
Introduces the assistant, presents suggested scheme topics, and provides a quick view of knowledge-base activity.

## Ask AI Assistant
Supports typed Tamil and English questions, suggested topics, follow-up question chips, bounded session chat history, answer display, source excerpts/links, and a clear-chat action. Vector, BM25, and Hybrid retrieval modes can be selected to compare evidence retrieval.

## Voice questions
A recording is transcribed to text and shown for review/editing before submission. The resulting question uses the same guardrail and answer path as typed input. This is speech-to-text input support; it does not imply automatic indexing of arbitrary audio or video files.

## Sources & Ingestion
Supports PDF uploads, supported HTTP/HTTPS HTML or PDF URLs, Government Order catalogue refresh, catalogue review/download, and selection of GO PDF URLs for ingestion. Catalogue refresh is a metadata workflow; an administrator chooses which documents to index.

## Knowledge Base Status
Displays source-registry and indexing information and supports CSV export.

## Input safety
`guardrails.py` rejects empty input, checks a defined set of prompt-injection patterns, and calls OpenAI moderation. It returns structured result categories and fails closed when moderation cannot be completed.

## Ingestion pipeline
The ingestion module extracts PDF/web text, normalizes it, chunks it with overlap, hashes source content for duplicate detection, creates embeddings, updates the persistent FAISS index, and records source metadata/status in SQLite. PDF pages with little extractable text can attempt OCR when Tesseract is available.

## Retrieval and answers
The retrieval module supports Vector, BM25, and Hybrid approaches; selected Tamil questions can receive targeted English query expansions. Hybrid retrieval uses Reciprocal Rank Fusion (RRF). Explicit fiscal-year questions have year-aware source filtering and a BM25 fallback path when vector retrieval returns no matching results. The QA layer supplies retrieved chunks to the chat model and returns answer/source data for the UI.

## Evidence and boundaries
The answer instructions prioritize retrieved context, source/page citations where available, and communicating evidence gaps. The Q&A path does not run a fresh web search for each question. Do not describe arbitrary image/video/embedded-audio indexing as implemented unless that extraction path has been added and tested.
