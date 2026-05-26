"""
Pydantic models for /v1/forecasts endpoints.
All models use camelCase JSON aliases to match the TypeScript frontend.
"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class HistoryPoint(CamelModel):
    """One month of historical demand."""
    month: str          # ISO-8601 YYYY-MM
    qty:   float


class ForecastPoint(CamelModel):
    """One month of demand forecast with prediction interval."""
    month: str          # ISO-8601 YYYY-MM
    mean:  float
    p10:   float        # lower 10th-percentile
    p90:   float        # upper 90th-percentile


class ForecastSeries(CamelModel):
    """Full forecast payload for one item × warehouse combination."""
    item_id:                  str
    warehouse_id:             str
    history:                  list[HistoryPoint]
    forecast:                 list[ForecastPoint]
    recommended_reorder_point: float
    recommended_safety_stock:  float
    model_version:            str
    as_of:                    str             # UTC ISO-8601
