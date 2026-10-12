# Change log — UI and voice update

This file records the UI/voice changes described in the current project notes. Add future entries chronologically and describe only changes that have been implemented and verified.

## UI and voice update

### Files modified

| File | Change |
|---|---|
| `app.py` | Added sidebar navigation for Home, Ask AI Assistant, Sources & Ingestion, and Knowledge Base Status; a home page; chat-style Ask page with history, suggested-scheme panel, follow-up chips, and voice input; and restyled administration/status pages. Existing administration and status functionality was organized into `render_sources_page()` and `render_status_page()`. |
| `.env.example` | Added optional, commented voice configuration settings. |

### Files added

| File | Purpose |
|---|---|
| `src/voice.py` | `transcribe_audio()` converts recorded audio into text for a spoken question. |
| `.streamlit/config.toml` | Defines the light green theme and disables usage statistics collection. |
| `tests/test_voice.py` | Voice transcription unit tests using mocks, without network calls. |
| `tests/test_ui_flow.py` | UI flow tests using Streamlit AppTest and a mocked backend. |

### Behaviour notes

- Typed, selected, and transcribed questions use the same question-processing path: guardrail check, embeddings/retrieval setup, then `answer_question(...)`.
- Voice input is transcribed to text and shown in the question box for review/editing before Send. Transcription requires an OpenAI API key and internet access.
- Chat history is session-based and bounded to the last 20 turns. Clearing chat or refreshing the session clears that history.
- Suggested topics and follow-up chips send complete questions; the retriever does not use conversational memory to interpret incomplete follow-ups.
- Suggested scheme topics are entry points for exploration; an answer depends on relevant material being indexed.
- Page navigation may reset page-local inputs such as selected upload files.
- The UI was tested with Streamlit 1.65. Custom CSS can look different across substantially different Streamlit versions.

### Fixes recorded

1. **Sample-question key collision:** sample buttons use stable keys (`sample_0`, `sample_1`, `sample_2`) rather than keys derived from question text.
2. **Secrets configuration:** when `OPENAI_API_KEY` is configured through Streamlit secrets, the app copies it into the environment so dependent modules can read it.

### Files reported unchanged in the UI/voice update

`src/ingestion.py`, `src/retrieval.py`, `src/qa.py`, `src/source_catalogue.py`, `guardrails.py`, `requirements.txt`, original test files, and `data/*`.
