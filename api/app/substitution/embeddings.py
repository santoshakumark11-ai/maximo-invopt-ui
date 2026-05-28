"""
Item-description embedding service.

Tries sentence-transformers (all-MiniLM-L6-v2, 384-dim, CPU-only) first.
Falls back to TF-IDF + truncated SVD (scikit-learn) when sentence-transformers
is unavailable (e.g. Python 3.13 where torch has no wheels yet).

Both paths produce a normalised float vector per item that is stored in-memory
(fast cosine via NumPy dot product).  For production scale (500k+ items),
migrate to pgvector — the interface is the same.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

_embeddings: Optional[dict[str, np.ndarray]] = None
_dim: int = 0

# ── Strategy selection ───────────────────────────────────────────────────────

try:
    from sentence_transformers import SentenceTransformer
    _ST_OK = True
except Exception:
    _ST_OK = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    _SK_OK = True
except Exception:
    _SK_OK = False


def _build_st(items: dict[str, str]) -> tuple[dict[str, np.ndarray], int]:
    """Sentence-transformer path — real semantic embeddings."""
    settings = get_settings()
    model = SentenceTransformer(settings.substitution_embedding_model)
    ids = list(items.keys())
    texts = [items[i] for i in ids]
    vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    dim = vecs.shape[1]
    return {ids[i]: vecs[i] for i in range(len(ids))}, dim


def _build_tfidf(items: dict[str, str]) -> tuple[dict[str, np.ndarray], int]:
    """TF-IDF fallback — bag-of-words similarity (no semantic understanding)."""
    dim = 128
    ids = list(items.keys())
    texts = [items[i] for i in ids]
    if len(texts) < 2:
        return {}, 0
    tfidf = TfidfVectorizer(max_features=5000, stop_words="english")
    X = tfidf.fit_transform(texts)
    svd = TruncatedSVD(n_components=min(dim, X.shape[1] - 1), random_state=42)
    reduced = svd.fit_transform(X)
    # L2 normalise for cosine via dot product.
    norms = np.linalg.norm(reduced, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    reduced = reduced / norms
    return {ids[i]: reduced[i] for i in range(len(ids))}, reduced.shape[1]


# ── Public surface ───────────────────────────────────────────────────────────

def build_index(items: dict[str, str]) -> None:
    """
    Build (or rebuild) the in-memory embedding index.

    items: {itemnum: "description text"}

    Called by the orchestrator after pulling MXAPIINVENTORY / MXAPIITEM.
    """
    global _embeddings, _dim
    if not items:
        _embeddings = {}
        _dim = 0
        return

    if _ST_OK:
        try:
            _embeddings, _dim = _build_st(items)
            logger.info("Embedding index built with sentence-transformers (%d items, dim=%d)",
                        len(_embeddings), _dim)
            return
        except Exception as exc:
            logger.warning("sentence-transformers failed (%s) — falling back to TF-IDF", exc)

    if _SK_OK:
        try:
            _embeddings, _dim = _build_tfidf(items)
            logger.info("Embedding index built with TF-IDF (%d items, dim=%d)",
                        len(_embeddings), _dim)
            return
        except Exception as exc:
            logger.warning("TF-IDF fallback failed: %s", exc)

    logger.warning("No embedding backend available — substitution recommender disabled")
    _embeddings = {}
    _dim = 0


def get_embedding(item_id: str) -> Optional[np.ndarray]:
    """
    Look up an embedding by item_id, trying uppercase first.

    NOTE: do NOT use `dict.get(a) or dict.get(b)` here — numpy arrays raise
    ValueError on __bool__ when they have more than one element.  Use
    explicit `is not None` checks.
    """
    if _embeddings is None:
        return None
    vec = _embeddings.get(item_id.upper())
    if vec is not None:
        return vec
    return _embeddings.get(item_id)


def find_nearest(item_id: str, top_k: int = 10, exclude: set[str] | None = None) -> list[tuple[str, float]]:
    """
    Return the top-K nearest items by cosine similarity (dot product on
    normalised vectors).  Excludes the query item itself.
    """
    if _embeddings is None or not _embeddings:
        return []
    query = get_embedding(item_id)
    if query is None:
        return []
    exclude = exclude or set()
    exclude.add(item_id.upper())
    exclude.add(item_id)

    # Vectorised dot product against all stored embeddings.
    ids = [k for k in _embeddings if k not in exclude]
    if not ids:
        return []
    matrix = np.stack([_embeddings[k] for k in ids])
    scores = matrix @ query  # cosine (both sides normalised)
    ranked = sorted(zip(ids, scores.tolist()), key=lambda t: t[1], reverse=True)
    return ranked[:top_k]


def is_ready() -> bool:
    return _embeddings is not None and len(_embeddings) > 0
