"""
In-memory forecast store — Phase 2/3 dev fixtures.
Seeded with 12 months of history + 12 months of forecast for the five main
items used in the recommendations store.
"""
from __future__ import annotations

from app.forecasts.models import ForecastPoint, ForecastSeries, HistoryPoint

# ── helpers ───────────────────────────────────────────────────────────────────

def _history(base: float, noise: list[float]) -> list[HistoryPoint]:
    months = [
        "2024-06", "2024-07", "2024-08", "2024-09",
        "2024-10", "2024-11", "2024-12", "2025-01",
        "2025-02", "2025-03", "2025-04", "2025-05",
    ]
    return [
        HistoryPoint(month=m, qty=max(0.0, round(base + d, 1)))
        for m, d in zip(months, noise)
    ]


def _forecast(base: float, trend: float, spread_pct: float) -> list[ForecastPoint]:
    months = [
        "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-10", "2025-11", "2025-12", "2026-01",
        "2026-02", "2026-03", "2026-04", "2026-05",
    ]
    points = []
    for i, m in enumerate(months):
        mean = round(base + trend * i, 2)
        spread = round(mean * spread_pct, 2)
        points.append(ForecastPoint(
            month=m,
            mean=mean,
            p10=round(max(0.0, mean - spread), 2),
            p90=round(mean + spread, 2),
        ))
    return points


# ── seed data ─────────────────────────────────────────────────────────────────

_STORE: dict[str, ForecastSeries] = {}


def _seed() -> None:
    seeds = [
        # (item_id, warehouse_id, hist_base, hist_noise, fc_base, fc_trend,
        #  spread_pct, rop, ss, model_version)
        (
            "PUMP-001", "WH-PERTH",
            4.0,
            [0.5, -0.3, 1.2, -0.5, 0.8, -1.0, 2.0, -0.2, 0.4, 1.1, -0.6, 0.7],
            4.2, 0.05, 0.30,
            12.0, 5.0, "v2.3.1",
        ),
        (
            "MOTOR-022", "WH-PERTH",
            2.0,
            [0.2, -0.1, 0.5, -0.3, 0.0, 0.4, -0.2, 0.6, -0.4, 0.3, 0.1, -0.5],
            2.1, 0.02, 0.35,
            7.0, 3.0, "v2.3.1",
        ),
        (
            "VALVE-042", "WH-PERTH",
            6.0,
            [1.0, -0.5, 2.0, -1.0, 0.5, 1.5, -0.8, 0.3, 1.2, -0.7, 0.9, -0.4],
            6.3, 0.08, 0.25,
            18.0, 7.0, "v2.3.1",
        ),
        (
            "BEAR-117", "WH-PERTH",
            10.0,
            [1.5, -1.0, 2.5, -0.5, 1.0, -2.0, 3.0, -0.5, 1.5, 0.5, -1.0, 1.0],
            10.5, 0.10, 0.20,
            30.0, 12.0, "v2.3.1",
        ),
        (
            "SEAL-009", "WH-PERTH",
            1.5,
            [0.5, 0.0, 1.0, -0.5, 0.5, -0.5, 0.5, 0.0, 1.0, -1.0, 0.5, 0.0],
            1.6, 0.01, 0.40,
            5.0, 2.0, "v2.3.1",
        ),
    ]

    for (item_id, warehouse_id, hbase, hnoise, fbase, ftrend,
         spread, rop, ss, mv) in seeds:
        key = f"{item_id}|{warehouse_id}"
        _STORE[key] = ForecastSeries(
            item_id=item_id,
            warehouse_id=warehouse_id,
            history=_history(hbase, hnoise),
            forecast=_forecast(fbase, ftrend, spread),
            recommended_reorder_point=rop,
            recommended_safety_stock=ss,
            model_version=mv,
            as_of="2025-06-01T00:00:00Z",
        )


_seed()


# ── public API ────────────────────────────────────────────────────────────────

def get_forecast(item_id: str, warehouse_id: str) -> ForecastSeries | None:
    return _STORE.get(f"{item_id.upper()}|{warehouse_id.upper()}")
