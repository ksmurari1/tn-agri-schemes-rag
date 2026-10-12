# Setup and operations

## Prerequisites
- Windows with Python 3.12 available as `py -3.12`.
- Valid OpenAI API credentials for the model-backed features being used.
- Playwright Chromium for the browser-based catalogue workflow.
- Local Tesseract OCR if OCR fallback is needed for scanned/low-text PDF pages.

## Setup in Windows Command Prompt

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
notepad .env
```

Set `OPENAI_API_KEY` in `.env`, then start:

```bat
streamlit run app.py
```

Run tests:

```bat
python -m pytest -q
```

## Configuration reference

Use `.env.example` as the current template. Common settings include:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Credential for OpenAI-backed functionality. |
| `OPENAI_CHAT_MODEL` | Chat model setting, where read by the application. |
| `OPENAI_EMBEDDING_MODEL` | Embedding model setting, where read by the application. |
| `OPENAI_MODERATION_MODEL` | Moderation model for input safety checks. |
| `TESSERACT_CMD` | Example path to the Tesseract executable. |
| `OPENAI_TRANSCRIBE_MODEL` | Optional transcription model setting. |
| `OPENAI_TRANSCRIBE_LANGUAGE` | Optional transcription language hint. |
| `OPENAI_TRANSCRIBE_PROMPT` | Optional spelling hints for transcription. |

Confirm a setting is read by the code before relying on it. Keep real credentials in `.env` or a secret store, never in version control.

## Data directories

| Path | Role | Guidance |
|---|---|---|
| `data/source_catalogue/` | Seed catalogue metadata (JSON, CSV, XLSX, README). | Keep curated inputs required by the project. |
| `data/uploads/` | Local uploaded source files. | Runtime files stay ignored; retain `.gitkeep` if needed. |
| `data/vector_store/` | Persistent FAISS index and document metadata. | Generated index files stay ignored; retain `.gitkeep` if needed. |
| `data/source_registry.sqlite3` | Local source/ingestion registry. | Runtime database stays ignored. |

## Ingestion operations
1. Prefer trusted official sources and approved PDFs.
2. Refresh the GO catalogue when metadata needs updating.
3. Review records before selecting documents for indexing.
4. Confirm the ingestion result and source status.
5. Ask a representative question about the new source.
6. Inspect the returned passage and page.

Exact-content hashing supports duplicate detection. Changed content can be registered as a new source version; review source records when managing updated or superseded documents.

## Backup and restore
Back up the FAISS index directory and SQLite source registry together for a consistent local knowledge-base backup. Preserve seed catalogue files if they are needed to reproduce the catalogue workflow. Do not include credentials in a shared backup.

After restoring, start the app, inspect Knowledge Base Status, and ask a question whose supporting source is known to exist.

## Operational checks
- For model configuration errors, check environment variables or hosting secrets.
- For catalogue refresh issues, verify network access and Playwright Chromium installation.
- For OCR, verify Tesseract installation and executable path.
- If evidence is missing, check ingestion, index state, retrieval mode, and source metadata.
- Rerun automated tests after code or dependency changes.
