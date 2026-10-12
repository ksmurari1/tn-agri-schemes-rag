from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import fitz
import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "source_registry.sqlite3"
VECTOR_DIR = DATA_DIR / "vector_store"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 180
USER_AGENT = "TamilNaduAgriSchemesRAG/0.1"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[\u00ad\u200b]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def init_registry() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sources (
          source_id TEXT PRIMARY KEY,
          source_name TEXT NOT NULL,
          source_url TEXT,
          source_type TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          chunk_count INTEGER NOT NULL DEFAULT 0,
          ingested_at_utc TEXT NOT NULL,
          message TEXT
        )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash)"
        )
        conn.commit()


def find_hash(content_hash: str) -> dict | None:
    init_registry()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sources WHERE content_hash=? AND status='indexed' LIMIT 1",
            (content_hash,),
        ).fetchone()
    return dict(row) if row else None


def source_rows() -> list[dict]:
    init_registry()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM sources ORDER BY ingested_at_utc DESC"
            ).fetchall()
        ]


def _record_source(
    source_id, name, url, source_type, content_hash, status, chunk_count, message=""
):
    init_registry()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
        INSERT INTO sources(source_id,source_name,source_url,source_type,content_hash,status,
                            chunk_count,ingested_at_utc,message)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET
          source_name=excluded.source_name, source_url=excluded.source_url,
          source_type=excluded.source_type, content_hash=excluded.content_hash,
          status=excluded.status, chunk_count=excluded.chunk_count,
          ingested_at_utc=excluded.ingested_at_utc, message=excluded.message
        """,
            (
                source_id,
                name,
                url,
                source_type,
                content_hash,
                status,
                chunk_count,
                datetime.now(UTC).isoformat(),
                message,
            ),
        )
        conn.commit()


def _pdf_documents(
    content: bytes, source_name: str, source_url: str | None, source_id: str
) -> list[Document]:
    """Extract PDF text page-by-page; OCR scanned/near-empty pages when configured."""
    docs = []
    ocr_pages = 0
    with fitz.open(stream=content, filetype="pdf") as pdf:
        for page_index, page in enumerate(pdf, start=1):
            text = normalize_text(page.get_text("text"))
            # A page with very little extractable text is likely scanned or image-based.
            if len(text) < 40:
                try:
                    import pytesseract

                    pytesseract.pytesseract.tesseract_cmd = (
                        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                    )

                    import io

                    from PIL import Image

                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pix.tobytes("png")))
                    language = os.getenv("TESSERACT_LANG", "eng+tam")
                    try:
                        ocr_text = pytesseract.image_to_string(image, lang=language)
                    except Exception:
                        # If Tamil trained data is unavailable, retry English OCR and record its limits.
                        ocr_text = pytesseract.image_to_string(image, lang="eng")
                    ocr_text = normalize_text(ocr_text)
                    if len(ocr_text) > len(text):
                        text = ocr_text
                        if text:
                            ocr_pages += 1
                except ImportError:
                    # Keep normal text extraction available even when OCR dependencies are absent.
                    pass
                except Exception as exc:
                    # Do not fail the entire PDF because one page's OCR failed.
                    print(f"OCR warning on {source_name}, page {page_index}: {exc}")
            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source_id": source_id,
                            "source_title": source_name,
                            "source_url": source_url or "",
                            "source_type": "pdf",
                            "page": page_index,
                            "extraction_method": (
                                "ocr"
                                if len(normalize_text(page.get_text("text"))) < 40
                                else "text"
                            ),
                        },
                    )
                )
    return docs


def _html_documents(
    content: bytes, source_name: str, source_url: str, source_id: str
) -> list[Document]:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    title = (
        normalize_text(soup.title.get_text(" ", strip=True))
        if soup.title
        else source_name
    )
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = normalize_text(main.get_text("\n", strip=True))
    if not text:
        raise ValueError("No readable text was extracted from this URL.")
    return [
        Document(
            page_content=text,
            metadata={
                "source_id": source_id,
                "source_title": title or source_name,
                "source_url": source_url,
                "source_type": "url",
                "page": None,
            },
        )
    ]


def read_url(url: str, timeout: int = 30) -> tuple[bytes, str, str]:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid http:// or https:// URL.")
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    content = response.content
    is_pdf = (
        "application/pdf" in content_type
        or url.lower().split("?")[0].endswith(".pdf")
        or content[:4] == b"%PDF"
    )
    return content, ("pdf" if is_pdf else "url"), response.url


def prepare_chunks(documents: Iterable[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(list(documents))
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["chunk_hash"] = hashlib.sha256(
            normalize_text(chunk.page_content).encode("utf-8")
        ).hexdigest()
    return chunks


def ingest_content(
    content: bytes,
    source_name: str,
    source_url: str | None,
    source_type: str,
    embeddings,
    vector_dir: Path = VECTOR_DIR,
) -> dict:
    """Idempotent ingestion by exact content hash; changed versions are retained."""
    init_registry()
    content_hash = sha256_bytes(content)
    existing = find_hash(content_hash)
    if existing:
        return {
            "status": "skipped_duplicate",
            "source_id": existing["source_id"],
            "chunks": existing["chunk_count"],
            "message": "Identical content already indexed.",
        }

    source_id = hashlib.sha256(
        ((source_url or source_name) + "|" + content_hash).encode("utf-8")
    ).hexdigest()[:24]
    if source_type == "pdf":
        docs = _pdf_documents(content, source_name, source_url, source_id)
    else:
        docs = _html_documents(content, source_name, source_url or "", source_id)
    chunks = prepare_chunks(docs)
    if not chunks:
        raise ValueError(
            "No extractable text was found. This PDF may be scanned and require OCR."
        )
    for chunk in chunks:
        chunk.metadata["content_hash"] = content_hash

    from langchain_community.vectorstores import FAISS

    vector_dir = Path(vector_dir)
    vector_dir.mkdir(parents=True, exist_ok=True)
    index_file = vector_dir / "index.faiss"
    if index_file.exists():
        store = FAISS.load_local(
            str(vector_dir), embeddings, allow_dangerous_deserialization=True
        )
        store.add_documents(chunks)
    else:
        store = FAISS.from_documents(chunks, embeddings)
    store.save_local(str(vector_dir))

    _record_source(
        source_id,
        source_name,
        source_url,
        source_type,
        content_hash,
        "indexed",
        len(chunks),
        f"Extracted {len(docs)} document section(s).",
    )
    return {
        "status": "indexed",
        "source_id": source_id,
        "chunks": len(chunks),
        "message": f"Indexed {len(chunks)} chunks.",
    }


def ingest_uploaded_file(uploaded_file, embeddings) -> dict:
    content = uploaded_file.getvalue()
    name = Path(uploaded_file.name).name
    if not (name.lower().endswith(".pdf") or content[:4] == b"%PDF"):
        raise ValueError(
            f"{name}: only PDF uploads are supported in this first ingestion milestone."
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / name).write_bytes(content)
    return ingest_content(content, name, None, "pdf", embeddings)


def ingest_url(url: str, embeddings) -> dict:
    content, source_type, final_url = read_url(url)
    name = Path(urlparse(final_url).path).name or urlparse(final_url).netloc
    return ingest_content(content, name, final_url, source_type, embeddings)


def get_vector_store(embeddings, vector_dir: Path = VECTOR_DIR):
    from langchain_community.vectorstores import FAISS

    vector_dir = Path(vector_dir)
    if not (vector_dir / "index.faiss").exists():
        return None
    return FAISS.load_local(
        str(vector_dir), embeddings, allow_dangerous_deserialization=True
    )
