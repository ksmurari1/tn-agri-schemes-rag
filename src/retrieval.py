from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Iterable

from langchain_core.documents import Document


def tokenize(text: str) -> list[str]:
    """Tokenize English and Tamil while preserving Unicode combining marks."""
    tokens: list[str] = []
    current: list[str] = []
    for char in (text or "").casefold():
        category = unicodedata.category(char)
        if char.isalnum() or category.startswith("M"):
            current.append(char)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens



def expand_retrieval_queries(question: str) -> list[str]:
    """Add targeted English retrieval queries for Tamil agriculture questions.

    The original question is always retained. These expansions affect retrieval
    only; answer generation should continue to use the farmer's original query.
    """
    original = (question or "").strip()
    if not original:
        return []

    queries = [original]
    q = original.casefold()
    is_tamil = any("\u0b80" <= char <= "\u0bff" for char in q)
    if not is_tamil:
        return queries

    # Existing Velaan e-Sevai expansion.
    mentions_velaan_eservice = any(
        term in q for term in ("வேளான்", "வேளாண்", "இ-சேவை", "இ சேவை", "இசேவை")
    )
    asks_about_services = any(
        term in q for term in ("சேவை", "சேவைகள்", "இலவச", "வழங்கப்படும்", "பட்டியலிட")
    )
    if mentions_velaan_eservice and asks_about_services:
        queries.append(
            "Velaan e-Sevai Maiyam Annexure II List of Services Provided "
            "Services Offered utility charges revised charges Free "
            "G.O.(D).No.230 Agriculture Farmers Welfare"
        )

    # Subsidy questions. Use both a general scheme query and topic-specific
    # queries so Tamil wording can retrieve English source documents.
    subsidy_terms = (
        "மானியம்", "மானிய", "மானியத்தை", "மானியத்", "உதவித்தொகை",
        "சலுகை", "விண்ணப்பிக்க", "விண்ணப்பம்", "விண்ணப்ப",
    )
    seed_terms = (
        "விதை", "விதைகள்", "மக்காச்சோள", "சான்றளிக்கப்பட்ட",
        "எண்ணெய் வித்து",
    )
    application_terms = (
        "எங்கு", "எப்படி", "யாரிடம்", "விண்ணப்ப", "தகுதி",
        "ஆவணங்கள்", "பெற வேண்டும்",
    )

    asks_about_subsidy = any(term in q for term in subsidy_terms)
    asks_about_seeds = any(term in q for term in seed_terms)
    asks_about_application = any(term in q for term in application_terms)

    if asks_about_subsidy or (asks_about_seeds and asks_about_application):
        queries.append(
            "Tamil Nadu Agricultural Inputs Subsidy Schemes "
            "farmer subsidy eligibility application procedure "
            "Agriculture and Farmers Welfare Department"
        )

    if asks_about_seeds:
        queries.append(
            "Agricultural Inputs Subsidy Schemes Tamil Nadu "
            "distribution of certified seeds of maize "
            "50% cost of seeds maximum Rs.1200 per quintal "
            "application Assistant Agricultural Officer "
            "Village Level Agricultural Officer"
        )

    if asks_about_subsidy and not asks_about_seeds:
        queries.append(
            "Tamil Nadu agriculture farmer subsidy amount how to apply "
            "eligibility Assistant Agricultural Officer"
        )

    # Stable de-duplication while preserving original-first ordering.
    return list(dict.fromkeys(queries))


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[Document]], k: int = 60, limit: int = 5
) -> list[Document]:
    """Combine ranked lists and deduplicate identical chunks using RRF."""
    scores: dict[str, float] = defaultdict(float)
    docs_by_key: dict[str, Document] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            metadata = doc.metadata or {}
            key = str(metadata.get("chunk_hash") or "")
            if not key:
                key = f"{metadata.get('source_id', '')}|{metadata.get('page', '')}|{doc.page_content}"
            docs_by_key[key] = doc
            scores[key] += 1.0 / (k + rank)
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)
    result = []
    for key in ordered[:limit]:
        doc = docs_by_key[key]
        doc.metadata = dict(doc.metadata or {})
        doc.metadata["hybrid_rrf_score"] = scores[key]
        result.append(doc)
    return result


def bm25_search(query: str, documents: list[Document], k: int = 5) -> list[Document]:
    """Rank existing document chunks using BM25 with a lexical fallback."""
    if not documents:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    from rank_bm25 import BM25Okapi
    corpus_tokens = [tokenize(doc.page_content) for doc in documents]
    valid_indices = [i for i, tokens in enumerate(corpus_tokens) if tokens]
    if not valid_indices:
        return []
    valid_documents = [documents[i] for i in valid_indices]
    valid_tokens = [corpus_tokens[i] for i in valid_indices]
    scores = BM25Okapi(valid_tokens).get_scores(query_tokens)
    query_set = set(query_tokens)
    overlap_counts = [len(query_set.intersection(set(tokens))) for tokens in valid_tokens]
    matching_indices = [i for i, count in enumerate(overlap_counts) if count > 0]
    if not matching_indices:
        return []
    if not any(scores[i] > 0 for i in matching_indices):
        ranked_indices = sorted(matching_indices, key=lambda i: overlap_counts[i], reverse=True)
    else:
        ranked_indices = sorted(matching_indices, key=lambda i: (scores[i], overlap_counts[i]), reverse=True)
    return [valid_documents[i] for i in ranked_indices[:max(0, k)]]


def _requested_year_scope(question: str) -> str | None:
    """Return a normalized fiscal-year scope only when the question explicitly names one."""
    q = (question or "").lower().replace("–", "-").replace("—", "-")
    patterns = [
        (r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", None),
        (r"\b(20\d{2})\s*[-/]\s*(\d{2})\b", None),
    ]
    for pattern, _ in patterns:
        match = re.search(pattern, q)
        if match:
            first, second = match.groups()
            if len(second) == 2:
                second = first[:2] + second
            return f"{first}-{second}"
    return None


def _source_matches_year(doc: Document, year_scope: str) -> bool:
    """Match fiscal-year references in source metadata, not chunk text."""
    metadata = doc.metadata or {}
    source_bits = " ".join(
        str(metadata.get(key, "")) for key in ("source_title", "source_url", "source_name")
    ).lower()
    source_bits = source_bits.replace("%20", " ").replace("–", "-").replace("—", "-")
    first, second = year_scope.split("-")
    short = second[-2:]
    normalized = re.sub(r"[^a-z0-9]+", " ", source_bits)
    compact = re.sub(r"[^a-z0-9]+", "", source_bits)
    candidates = [
        f"{first}-{second}", f"{first}_{short}", f"{first} {second}",
        f"{first} {short}", f"{first}{short}", f"{first}_{second}",
    ]
    return any(c.replace("-", "").replace("_", "").replace(" ", "") in compact for c in candidates) or any(c in normalized for c in candidates)


def _filter_year(documents: list[Document], question: str) -> tuple[list[Document], str | None]:
    year_scope = _requested_year_scope(question)
    if not year_scope:
        return documents, None
    scoped = [doc for doc in documents if _source_matches_year(doc, year_scope)]
    # Only apply a filter if the corpus contains a recognizable matching source.
    # Otherwise keep the normal retrieval result and let the model report evidence gaps.
    return (scoped, year_scope) if scoped else (documents, None)


def retrieve_documents(store, question: str, mode: str = "vector", k: int = 5) -> list[Document]:
    """Retrieve from the existing FAISS corpus using vector, BM25 or hybrid.

    Tamil questions about the known Velaan e-Sevai Maiyam service list receive
    an additional English retrieval query. The existing indexed corpus is reused.
    Explicit fiscal-year filtering remains based on the original question.
    """
    if mode not in {"vector", "bm25", "hybrid"}:
        raise ValueError("mode must be 'vector', 'bm25', or 'hybrid'")

    docstore = getattr(store, "docstore", None)
    corpus_dict = getattr(docstore, "_dict", {}) if docstore else {}
    corpus = list(corpus_dict.values())
    scoped_corpus, year_scope = _filter_year(corpus, question)
    queries = expand_retrieval_queries(question)
    if not queries:
        return []

    # Keep the original path simple when no expansion is needed.
    expanded = len(queries) > 1

    if mode == "bm25":
        ranked_lists = [bm25_search(query, scoped_corpus, k=k) for query in queries]
        if not expanded:
            return ranked_lists[0]
        return reciprocal_rank_fusion(ranked_lists, limit=k)

    ranked_lists: list[list[Document]] = []
    search_k = max(k * 8, 30) if year_scope else (max(k * 4, 20) if expanded else k)

    for query in queries:
        vector_docs = store.similarity_search(query, k=search_k)
        if year_scope:
            vector_docs = [doc for doc in vector_docs if _source_matches_year(doc, year_scope)]
        vector_docs = vector_docs[:k]
        ranked_lists.append(vector_docs)

        if mode == "hybrid":
            keyword_docs = bm25_search(query, scoped_corpus, k=k)
            ranked_lists.append(keyword_docs)

    if mode == "vector" and not expanded:
        vector_docs = ranked_lists[0]
        if year_scope and not vector_docs:
            # Preserve the existing deterministic fallback for explicit year queries.
            return bm25_search(question, scoped_corpus, k=k)
        return vector_docs

    # Expanded vector searches and hybrid searches combine rankings from each query.
    results = reciprocal_rank_fusion(ranked_lists, limit=k)
    if year_scope and not results and mode == "vector":
        return bm25_search(question, scoped_corpus, k=k)
    return results
