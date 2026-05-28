"""
Hybrid substitution recommender — DLD §4.4, §8.4.

Scoring weights (DLD §8.4):
    0.45 × cross_ref_match        (binary: 1 if ALTITEM exists)
    0.25 × embedding_cosine_sim   (0..1 from vector store)
    0.15 × historical_co_use_rate (0..1 — deferred to Q3, placeholder 0.5)
    0.10 × stock_on_hand_norm     (0..1 — curbal / max_curbal in the result set)
    0.05 × vendor_reliability     (0..1 — on_time_pct from vendor block)

Retrieval order:
    1. Deterministic cross-reference cache (ALTITEM from Maximo).
    2. Embedding cosine top-K via embeddings.find_nearest.
    3. Merge, rerank by composite score, return top-N.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from app.config import get_settings
from app.substitution import embeddings

logger = logging.getLogger(__name__)


@dataclass
class SubstituteResult:
    item_id: str
    description: str
    score: float
    source: str            # "cross_ref" | "embedding" | "both"
    confidence: float      # 0..1
    stock_on_hand: float
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None


# ── Cross-reference cache ────────────────────────────────────────────────────

_cross_refs: dict[str, list[str]] = {}


def load_cross_refs(refs: dict[str, list[str]]) -> None:
    """Load ALTITEM cross-reference map.  Called by the orchestrator."""
    global _cross_refs
    _cross_refs = {k.upper(): [v.upper() for v in vs] for k, vs in refs.items()}
    logger.info("Cross-reference cache loaded: %d items with alternates", len(_cross_refs))


# ── Inventory snapshot for stock-on-hand and descriptions ────────────────────

_inventory_snap: dict[str, dict[str, Any]] = {}


def load_inventory_snapshot(records: list[dict[str, Any]]) -> None:
    """Cache the latest inventory pull for stock-on-hand lookups during scoring."""
    global _inventory_snap
    _inventory_snap = {}
    for r in records:
        itemnum = str(r.get("itemnum") or r.get("spi:itemnum") or "").upper()
        if itemnum:
            _inventory_snap[itemnum] = r


def _get_val(row: dict, *keys: str) -> Any:
    for k in keys:
        for cand in (k, f"spi:{k}"):
            v = row.get(cand)
            if v is not None:
                return v
    return None


def _curbal(item_id: str) -> float:
    row = _inventory_snap.get(item_id.upper())
    if not row:
        return 0.0
    try:
        return float(_get_val(row, "curbal") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _description(item_id: str) -> str:
    row = _inventory_snap.get(item_id.upper())
    if not row:
        return ""
    item_obj = row.get("item") or row.get("spi:item") or {}
    return str(item_obj.get("description") or item_obj.get("spi:description") or "")


# ── Scoring ──────────────────────────────────────────────────────────────────

def _score(
    item_id: str,
    *,
    is_cross_ref: bool,
    cosine_sim: float,
    max_curbal: float,
) -> float:
    """DLD §8.4 composite score."""
    cross_ref_val = 1.0 if is_cross_ref else 0.0
    co_use = 0.5  # placeholder — deferred to Q3 when usage telemetry is wired
    stock_norm = min(1.0, _curbal(item_id) / max_curbal) if max_curbal > 0 else 0.0
    vendor_rel = 0.85  # neutral default

    return (
        0.45 * cross_ref_val
        + 0.25 * cosine_sim
        + 0.15 * co_use
        + 0.10 * stock_norm
        + 0.05 * vendor_rel
    )


# ── Public surface ───────────────────────────────────────────────────────────

def find_substitutes(
    item_id: str,
    *,
    top_k: Optional[int] = None,
) -> list[SubstituteResult]:
    """
    Hybrid retrieval: cross-ref first, then embedding similarity, merge + rerank.
    """
    settings = get_settings()
    top_k = top_k or settings.substitution_top_k

    candidates: dict[str, dict[str, Any]] = {}  # item_id → {source, cosine_sim}

    # ── Step 1: deterministic cross-references ────────────────────────────
    refs = _cross_refs.get(item_id.upper(), [])
    for ref_id in refs:
        candidates[ref_id] = {"source": "cross_ref", "cosine_sim": 1.0}

    # ── Step 2: embedding cosine top-K ────────────────────────────────────
    if embeddings.is_ready():
        nearest = embeddings.find_nearest(
            item_id, top_k=top_k * 3,  # over-retrieve for reranking
            exclude={item_id.upper()},
        )
        for cand_id, sim in nearest:
            if cand_id in candidates:
                candidates[cand_id]["source"] = "both"
                candidates[cand_id]["cosine_sim"] = max(
                    candidates[cand_id]["cosine_sim"], sim,
                )
            else:
                candidates[cand_id] = {"source": "embedding", "cosine_sim": sim}

    if not candidates:
        return []

    # ── Step 3: compute composite score + rerank ──────────────────────────
    all_curbals = [_curbal(cid) for cid in candidates]
    max_curbal = max(all_curbals) if all_curbals else 1.0

    results: list[SubstituteResult] = []
    for cid, info in candidates.items():
        composite = _score(
            cid,
            is_cross_ref=(info["source"] in ("cross_ref", "both")),
            cosine_sim=info["cosine_sim"],
            max_curbal=max_curbal,
        )
        results.append(SubstituteResult(
            item_id=cid,
            description=_description(cid),
            score=round(composite, 3),
            source=info["source"],
            confidence=round(min(1.0, composite), 2),
            stock_on_hand=_curbal(cid),
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
