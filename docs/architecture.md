# Architecture

## Design goals
The application separates user experience, input safety, source preparation, retrieval/answer generation, and evidence presentation.

## High-level architecture

```mermaid
flowchart TB
  subgraph UI["Streamlit experience — app.py"]
    HOME[Home]
    ASK[Ask AI Assistant]
    ADMIN[Sources & Ingestion]
    STATUS[Knowledge Base Status]
  end
  subgraph Q["Question path"]
    INPUT[Typed / suggested / transcribed question]
    GUARD[guardrails.py]
    QA[src/qa.py]
    RET[src/retrieval.py]
    ANS[Grounded answer + source details]
  end
  subgraph K["Knowledge preparation"]
    PDF[PDF upload]
    URL[HTML / PDF URL]
    GO[GO catalogue refresh and review]
    ING[src/ingestion.py]
    CHUNK[Chunking]
    EMB[Embeddings]
    FAISS[(Persistent FAISS index)]
    SQL[(SQLite source registry)]
  end
  ASK --> INPUT --> GUARD --> QA --> RET --> FAISS
  RET --> QA --> ANS --> ASK
  ADMIN --> PDF
  ADMIN --> URL
  ADMIN --> GO --> URL
  PDF --> ING
  URL --> ING
  ING --> CHUNK --> EMB --> FAISS
  ING --> SQL --> STATUS
```

## Component responsibilities

| Component | Responsibility |
|---|---|
| `app.py` | Page navigation, chat interaction, source administration, catalogue selection, status display, voice UI, and presentation. |
| `guardrails.py` | Empty-input handling, prompt-injection pattern checks, and moderation gate. |
| `src/ingestion.py` | PDF/URL reading, extraction, normalization, chunking, hashing, index updates, and registry writes. |
| `src/source_catalogue.py` | Government Order catalogue refresh and preparation of records for review. |
| `src/retrieval.py` | Tokenization, query expansion, BM25, year-aware filtering, and RRF ranking. |
| `src/qa.py` | Loads the knowledge base, retrieves context, invokes the chat model, and returns answer/source data. |
| `src/voice.py` | Converts recorded question audio to text. |
| `tests/` | Automated checks for retrieval, catalogue, UI flow, voice, and year-aware behaviour. |

## Persistence

```mermaid
flowchart LR
  S[Approved PDF / URL] --> X[Extract and normalize]
  X --> H[SHA-256 content hash]
  H --> C[Chunk text]
  C --> E[Generate embeddings]
  E --> F[(data/vector_store/ FAISS)]
  H --> D[(data/source_registry.sqlite3)]
  F --> R[Question retrieval]
  D --> ST[Status reporting]
```

FAISS holds searchable vector representations and associated document data. SQLite stores source-level ingestion metadata, status, and chunk counts. Back up both consistently when preserving a local knowledge base.

## Question lifecycle

```mermaid
sequenceDiagram
  actor User
  participant UI as Streamlit UI
  participant S as guardrails.py
  participant QA as src/qa.py
  participant R as src/retrieval.py
  participant F as FAISS
  participant L as Chat model
  User->>UI: Ask question
  UI->>S: Check question
  alt Blocked or moderation unavailable
    S-->>UI: Block result and message
  else Allowed
    S-->>UI: Allowed
    UI->>QA: answer_question(...)
    QA->>R: Retrieve relevant chunks
    R->>F: Search indexed content
    F-->>R: Ranked chunks
    R-->>QA: Context and metadata
    QA->>L: Answer from supplied context
    L-->>QA: Answer
    QA-->>UI: Answer and sources
    UI-->>User: Display answer and evidence
  end
```

## Trust and configuration
- Keep real credentials in `.env` or the hosting platform's secret store, never in Git.
- Catalogue refresh is separate from question answering.
- Question answering uses indexed context and does not perform live web search for each question.
- Treat local index files as runtime data, not source code.
