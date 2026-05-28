"""
Recommendation service — single async surface used by the router.

At runtime the service chooses between:
    - the DB repo (app.recommendations.repo)   when db.is_enabled() is True
    - the in-memory store (app.recommendations.store)  otherwise

This means the existing demo path (no DB, hard-coded seed fallback) continues
to work unchanged, while production gets the real persistence + audit chain.
"""
from __future__ import annotations

import logging
from typing import Optional

from app import db
from app.recommendations import store as mem_store
from app.recommendations.models import RecommendationDetail

logger = logging.getLogger(__name__)


def _use_db() -> bool:
    return db.is_enabled()


async def list_all() -> list[RecommendationDetail]:
    if _use_db():
        from app.recommendations import repo
        return await repo.get_all()
    return mem_store.get_all()


async def get_one(rec_id: str) -> Optional[RecommendationDetail]:
    if _use_db():
        from app.recommendations import repo
        return await repo.get_one(rec_id)
    return mem_store.get_one(rec_id)


async def update_status(
    rec_id: str, new_status: str, actor: str, detail: Optional[str] = None,
) -> Optional[RecommendationDetail]:
    if _use_db():
        from app.recommendations import repo
        return await repo.update_status(rec_id, new_status, actor, detail)
    # In-memory fallback. update_status raises on missing key — guard caller.
    if mem_store.get_one(rec_id) is None:
        return None
    return mem_store.update_status(rec_id, new_status, actor, detail)


async def edit_recommendation(
    rec_id: str, recommended_value: float, justification: str,
    expected_version: int, actor: str,
) -> Optional[RecommendationDetail]:
    if _use_db():
        from app.recommendations import repo
        return await repo.edit_recommendation(
            rec_id, recommended_value, justification, expected_version, actor,
        )
    return mem_store.edit_recommendation(
        rec_id, recommended_value, justification, expected_version, actor,
    )


async def seed_from_live_data(records: list[dict]) -> int:
    """Generate from live MXAPIINVENTORY and persist to whichever backend is active."""
    from app.recommendations.generator import generate_from_inventory
    recs = generate_from_inventory(records)

    if _use_db():
        from app.recommendations import repo
        n = await repo.replace_all(recs)
        for r in recs:
            await repo.write_initial_audit(r.rec_id)
        logger.info("Seeded %d recommendations into DB from %d inventory records", n, len(records))
        return n

    # In-memory fallback — preserve existing behaviour exactly.
    return mem_store.seed_from_live_data(records)
