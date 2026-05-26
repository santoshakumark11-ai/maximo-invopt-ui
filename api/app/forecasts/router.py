"""
Forecasts router — /v1/forecasts

GET  /v1/forecasts/{item_id}/{warehouse_id}   demand history + forecast series

Resolution order:
  1. Live data — fetch MATUSETRANS via MXAPIINVENTORY sub-collection ref.
  2. Seed fallback — return the hardcoded fixture if Maximo is unreachable
     or returns no transactions for this item.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.dependencies import CurrentUser, get_current_user
from app.forecasts import store as fc_store
from app.forecasts.maximo_client import fetch_item_forecast
from app.forecasts.models import ForecastSeries

router = APIRouter()

UserDep     = Annotated[CurrentUser, Depends(get_current_user)]
SettingsDep = Annotated[Settings,    Depends(get_settings)]


@router.get(
    "/{item_id}/{warehouse_id}",
    response_model=ForecastSeries,
    response_model_by_alias=True,
    summary="Get demand history and forecast for an item × warehouse",
)
async def get_forecast(
    item_id:      str,
    warehouse_id: str,
    settings:     SettingsDep,
    _user:        UserDep,
) -> ForecastSeries:
    # 1. Try live Maximo data first
    live = await fetch_item_forecast(settings, item_id, warehouse_id)
    if live is not None:
        return live

    # 2. Fall back to seed fixtures
    seed = fc_store.get_forecast(item_id, warehouse_id)
    if seed is not None:
        return seed

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"No forecast data found for item '{item_id}' "
            f"in warehouse '{warehouse_id}'"
        ),
    )
