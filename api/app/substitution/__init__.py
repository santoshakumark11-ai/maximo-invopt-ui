"""
Substitution recommender — DLD §4.4, §7.3, §8.4.

Hybrid retrieval:
    1. Deterministic cross-reference (ALTITEM) — sub-100ms cache path.
    2. Embedding cosine similarity — sentence-transformers or TF-IDF fallback.
    3. Rerank by stock-on-hand, on-time rate, historical co-use.

Public surface: recommender.find_substitutes(item_id, settings) → list[SubstituteResult].
"""
