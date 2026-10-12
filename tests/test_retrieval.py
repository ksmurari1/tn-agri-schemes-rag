from langchain_core.documents import Document

from src.retrieval import (
    bm25_search,
    reciprocal_rank_fusion,
    tokenize,
    expand_retrieval_queries,
)


def test_tokenize_handles_english_and_tamil_words():
    tokens = tokenize("PM-KUSUM scheme விவசாயி 2026")
    assert "pm" in tokens and "kusum" in tokens
    assert any(token for token in tokens if token.isdigit())
    assert any("விவசாயி" in token for token in tokens)


def test_bm25_prefers_keyword_match():
    docs = [
        Document(page_content="Solar pump subsidy under PM KUSUM scheme", metadata={"chunk_hash": "a"}),
        Document(page_content="Paddy procurement and minimum support price", metadata={"chunk_hash": "b"}),
    ]
    result = bm25_search("PM KUSUM solar pump", docs, k=2)
    assert result and result[0].metadata["chunk_hash"] == "a"


def test_rrf_combines_and_deduplicates_ranked_lists():
    a = Document(page_content="PM KUSUM", metadata={"chunk_hash": "a"})
    b = Document(page_content="Paddy price", metadata={"chunk_hash": "b"})
    result = reciprocal_rank_fusion([[a, b], [a]], limit=5)
    assert [d.metadata["chunk_hash"] for d in result] == ["a", "b"]
    assert result[0].metadata["hybrid_rrf_score"] > result[1].metadata["hybrid_rrf_score"]



def test_tamil_maize_subsidy_query_expands_to_english_terms():
    question = (
        "மக்காச்சோள சான்றளிக்கப்பட்ட விதைகளைப் பெற "
        "விவசாயிகள் எங்கு விண்ணப்பிக்க வேண்டும்? மானியம் எவ்வளவு?"
    )
    queries = expand_retrieval_queries(question)
    assert queries[0] == question
    assert any("certified seeds of maize" in q.casefold() for q in queries[1:])
    assert any("1200 per quintal" in q.casefold() for q in queries[1:])


def test_tamil_velaan_eservice_expansion_is_preserved():
    question = "வேளான் இ-சேவை மையத்தில் என்னென்ன சேவைகள் வழங்கப்படுகின்றன?"
    queries = expand_retrieval_queries(question)
    assert queries[0] == question
    assert any("Velaan e-Sevai Maiyam" in q for q in queries)


def test_english_query_is_not_expanded():
    question = "What is the subsidy for certified maize seeds?"
    assert expand_retrieval_queries(question) == [question]


def test_tamil_subsidy_word_expands():
    queries = expand_retrieval_queries("மானியம்")
    assert queries[0] == "மானியம்"
    assert any("farmer subsidy" in q.casefold() for q in queries[1:])
