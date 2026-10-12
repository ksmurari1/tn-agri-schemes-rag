from src.source_catalogue import canonical_url, normalize_space


def test_normalize_space():
    assert normalize_space("  Agriculture \n  Scheme ") == "Agriculture Scheme"


def test_canonical_url():
    assert (
        canonical_url(" https://example.gov/a.pdf&amp;x=1 ")
        == "https://example.gov/a.pdf&x=1"
    )
