from langchain_core.documents import Document
from src.retrieval import _requested_year_scope, _source_matches_year, _filter_year


def test_detects_fiscal_year_in_question():
    assert _requested_year_scope("Use the 2024–2025 Budget Speech only") == "2024-2025"


def test_matches_budget_filename_metadata():
    doc = Document(page_content="organic farming", metadata={
        "source_title": "TN%20agri_budget_speech_e_2024_25.pdf",
        "source_url": "https://example.test/TN%20agri_budget_speech_e_2024_25.pdf",
    })
    assert _source_matches_year(doc, "2024-2025")


def test_year_filter_keeps_matching_source():
    docs = [
        Document(page_content="old", metadata={"source_title": "TN_agri_budget_speech_e_2023_24.pdf"}),
        Document(page_content="new", metadata={"source_title": "TN_agri_budget_speech_e_2024_25.pdf"}),
    ]
    filtered, scope = _filter_year(docs, "Tell me about 2024-2025 Budget Speech")
    assert scope == "2024-2025"
    assert len(filtered) == 1
    assert "2024_25" in filtered[0].metadata["source_title"]
