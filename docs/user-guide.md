# User guide

## Ask a question
1. Open **Ask AI Assistant**.
2. Enter a Tamil or English question, or record a voice question.
3. Review/edit the voice transcript before sending.
4. Choose Vector, BM25, or Hybrid retrieval.
5. Select Send.
6. Read the answer and expand source details to inspect the evidence.

### Retrieval choices
- **Vector:** semantic similarity search over indexed chunks.
- **BM25:** lexical/token-based ranking.
- **Hybrid:** combines ranked results with Reciprocal Rank Fusion where applicable.

## Example questions
Adapt these examples to the sources actually indexed:
- “What assistance is described for micro irrigation?”
- “Which documents are mentioned for this application?”
- “Summarize the eligibility conditions stated in this Government Order.”
- “For financial year 2024–25, what does the indexed document say about the scheme?”
- “இந்தத் திட்டத்திற்கு என்ன தகுதி நிபந்தனைகள் குறிப்பிடப்பட்டுள்ளன?”

These prompts are examples, not a claim that every topic or year is already present in the index.

## Review the evidence
Expand the displayed source details, check title/page/excerpt/link, and open the original source when exact conditions, deadlines, or amounts matter. If evidence is missing, verify that the relevant document was ingested and indexed.

## Add trusted sources
1. Open **Sources & Ingestion**.
2. Upload a PDF or enter a trusted HTTP/HTTPS URL.
3. For Government Orders, refresh and review the catalogue.
4. Select relevant GO PDF URLs.
5. Run ingestion and review its outcome.
6. Confirm the source in **Knowledge Base Status**.

Catalogue refresh alone does not ingest all listed documents.

## Voice and chat history
Voice input produces editable text before submission. Chat history is bounded to the last 20 turns in the current session. Use Clear chat to reset it. Follow-up chips send complete questions; the retriever does not infer missing context from prior turns.

## Responsible verification
Check the original source wording, issue date, page, financial year, and whether a document describes a historical or current rule. Use the assistant to locate and summarize indexed evidence, not as a replacement for an official document or authorized scheme administrator.
