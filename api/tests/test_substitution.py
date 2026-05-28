"""
Unit tests for the substitution recommender.
"""
import pytest

from app.substitution import embeddings, recommender


@pytest.fixture(autouse=True)
def clear_state():
    # Reset module-level state between tests.
    embeddings._embeddings = None  # type: ignore[attr-defined]
    embeddings._dim = 0            # type: ignore[attr-defined]
    recommender._cross_refs = {}   # type: ignore[attr-defined]
    recommender._inventory_snap = {}  # type: ignore[attr-defined]
    yield


def test_embedding_index_builds():
    items = {
        "BEAR-001": "Ball bearing 6205 stainless steel",
        "BEAR-002": "Ball bearing 6205 carbon steel",
        "PUMP-001": "Centrifugal pump 3 inch 15HP",
        "VALVE-001": "Gate valve 4 inch class 150",
    }
    embeddings.build_index(items)
    assert embeddings.is_ready()


def test_nearest_finds_similar_descriptions():
    items = {
        "BEAR-001": "Ball bearing 6205 stainless steel",
        "BEAR-002": "Ball bearing 6205 carbon steel",
        "BEAR-003": "Roller bearing 6210",
        "PUMP-001": "Centrifugal pump 3 inch 15HP",
        "VALVE-001": "Gate valve 4 inch class 150",
    }
    embeddings.build_index(items)
    nearest = embeddings.find_nearest("BEAR-001", top_k=2)
    assert nearest, "expected at least one neighbour"
    # Two bearing variants should rank above pump/valve.
    top_ids = [t[0] for t in nearest]
    assert "BEAR-002" in top_ids or "BEAR-003" in top_ids


def test_recommender_returns_cross_refs_first():
    embeddings.build_index({
        "BEAR-001": "Ball bearing 6205 stainless steel",
        "BEAR-002": "Ball bearing 6205 carbon steel",
        "ALT-001":  "Substitute bearing identical part",
    })
    recommender.load_cross_refs({"BEAR-001": ["ALT-001"]})
    recommender.load_inventory_snapshot([
        {"itemnum": "ALT-001", "curbal": 50,
         "item": {"description": "Substitute bearing identical part"}},
        {"itemnum": "BEAR-002", "curbal": 5,
         "item": {"description": "Ball bearing 6205 carbon steel"}},
    ])
    results = recommender.find_substitutes("BEAR-001", top_k=5)
    assert len(results) >= 1
    # Cross-ref should dominate scoring.
    sources = {r.source for r in results}
    assert "cross_ref" in sources or "both" in sources


def test_recommender_returns_empty_when_no_index():
    # No embeddings built, no cross-refs → empty.
    results = recommender.find_substitutes("UNKNOWN", top_k=5)
    assert results == []
