"""
Substitution router — /v1/substitutes

GET  /v1/substitutes/{item}          Top-K substitute items (DLD §7.3)
"""
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user
from app.substitution.recommender import find_substitutes, SubstituteResult

logger = logging.getLogger(__name__)
router = APIRouter()

UserDep     = Annotated[CurrentUser, Depends(get_current_user)]
SettingsDep = Annotated[Settings,    Depends(get_settings)]


@router.get("/{item}", summary="Find substitute items (DLD §7.3)")
async def get_substitutes(
    item: str,
    _user: UserDep,
    top_k: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict]:
    """
    Returns ranked substitute items with score, source, confidence, and
    stock-on-hand.

    The embedding index must be built first (done by the orchestrator
    during :run or nightly batch).  If the index is empty, returns [].
    """
    results = find_substitutes(item, top_k=top_k)
    return [
        {
            "itemId":       r.item_id,
            "description":  r.description,
            "score":        r.score,
            "source":       r.source,
            "confidence":   r.confidence,
            "stockOnHand":  r.stock_on_hand,
            "vendorId":     r.vendor_id,
            "vendorName":   r.vendor_name,
        }
        for r in results
    ]
