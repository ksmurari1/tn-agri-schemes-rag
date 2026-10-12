# Editable diagram source

These Mermaid diagrams can be rendered by GitHub and compatible Markdown viewers. Keeping the source in version control makes the diagrams editable.

## End-to-end workflow

```mermaid
flowchart TD
    A[Trusted source material] --> B[PDF / HTML extraction]
    B --> C[Text normalization]
    C --> D[Chunking]
    D --> E[Embeddings]
    E --> F[(FAISS vector index)]
    C --> G[(SQLite source registry)]
    H[User question] --> I[Input guardrails]
    I --> J[Vector / BM25 / Hybrid retrieval]
    F --> J
    J --> K[Relevant passages]
    K --> L[Answer generation from context]
    L --> M[Answer and source evidence]
```

## Retrieval comparison

```mermaid
flowchart LR
    Q[Question] --> V[Vector retrieval]
    Q --> B[BM25 lexical retrieval]
    V --> RV[Ranked vector results]
    B --> RB[Ranked lexical results]
    RV --> F[RRF fusion when applicable]
    RB --> F
    F --> H[Hybrid results]
    RV --> OUT[Inspect top passages]
    RB --> OUT
    H --> OUT
```

## Administrator workflow

```mermaid
flowchart TD
    START[Sources & Ingestion] --> CHOICE{Source type}
    CHOICE -->|PDF file| UPLOAD[Upload PDF]
    CHOICE -->|Trusted URL| URL[Read HTML / PDF URL]
    CHOICE -->|Government Order| REFRESH[Refresh GO catalogue]
    REFRESH --> REVIEW[Review catalogue records]
    REVIEW --> SELECT[Select relevant PDF URLs]
    SELECT --> URL
    UPLOAD --> EXTRACT[Extract and normalize text]
    URL --> EXTRACT
    EXTRACT --> DEDUPE[Content hash / duplicate check]
    DEDUPE --> SPLIT[Split into chunks]
    SPLIT --> INDEX[Create embeddings and update FAISS]
    INDEX --> REGISTER[Update SQLite registry]
    REGISTER --> STATUS[Verify Knowledge Base Status]
```
