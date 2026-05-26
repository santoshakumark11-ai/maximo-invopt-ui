"""
In-memory store for recommendations.

On startup (see main.py lifespan) seed_from_live_data() is called with live
MXAPIINVENTORY records.  If Maximo is unavailable the hardcoded seed below
is used as a fallback so the UI always has something to show.
"""
from __future__ import annotations
import copy
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from app.recommendations.models import RecommendationDetail, AuditEvent, Rationale, \
    FeatureContribution, VendorInfo, LinkedAsset

logger = logging.getLogger(__name__)

_NOW = datetime.now(timezone.utc)
_EXPIRES = (_NOW + timedelta(days=7)).isoformat().replace("+00:00", "Z")
_CREATED = (_NOW - timedelta(hours=8)).isoformat().replace("+00:00", "Z")
_TS = _NOW.isoformat().replace("+00:00", "Z")


def _audit_created(extra: list[AuditEvent] | None = None) -> list[AuditEvent]:
    base = [
        AuditEvent(ts=_CREATED, actor="system", event="CREATED"),
        AuditEvent(ts=_CREATED, actor="system", event="NOTIFIED",
                   detail="Sent to planner inbox"),
    ]
    return base + (extra or [])


_VENDOR_ACME = VendorInfo(
    vendor_id="V-001", name="Acme Industrial Supply",
    mean_lead_days=14, std_lead_days=4, on_time_pct=0.88,
    unit_cost=260.0, holding_cost_pct=0.22, order_cost=85.0,
)
_VENDOR_BETA = VendorInfo(
    vendor_id="V-002", name="Beta Parts & Equipment",
    mean_lead_days=21, std_lead_days=6, on_time_pct=0.92,
    unit_cost=1_420.0, holding_cost_pct=0.20, order_cost=120.0,
)
_VENDOR_GAMMA = VendorInfo(
    vendor_id="V-003", name="Gamma Seals & Bearings",
    mean_lead_days=10, std_lead_days=3, on_time_pct=0.95,
    unit_cost=48.0, holding_cost_pct=0.25, order_cost=55.0,
)

_STORE: dict[str, RecommendationDetail] = {r.rec_id: r for r in [

    # ── ROP reductions ────────────────────────────────────────────────────────

    RecommendationDetail(
        rec_id="REC-001", item_id="PUMP-001",
        item_description="Centrifugal Pump 3\" 15HP", warehouse_id="BEDFORD/STORE-01",
        type="ROP", criticality="HIGH",
        current_value=32, recommended_value=18,
        delta_working_capital=11_440.0, confidence=0.92,
        status="NEW", version=1, created_at=_CREATED,
        wc_release=11_440.0, stock_out_risk_change_pct=-0.4,
        model_version="demand-forecast/sbj@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="intermittent", adi=1.7, cv_squared=0.61,
            twelve_month_mean_qty=84, lead_time_days_mean=14, lead_time_days_std=4,
            service_level_target=0.99,
            summary_text="**Intermittent demand** pattern detected (ADI 1.7, CV² 0.61). "
                         "Croston/SBJ model projects mean monthly demand of 7 units. "
                         "Current ROP of 32 carries 14 units of excess safety stock "
                         "at β=0.99. Recommended ROP of 18 releases ~$11k working capital "
                         "while maintaining the 99% service-level target.",
        ),
        feature_contributions=[
            FeatureContribution(name="asset_criticality_rollup", value="HIGH", contribution=0.42),
            FeatureContribution(name="lead_time_std", value=4, contribution=0.28),
            FeatureContribution(name="12m_mean_qty", value=84, contribution=0.18),
            FeatureContribution(name="on_time_rate", value=0.88, contribution=0.08),
            FeatureContribution(name="unit_cost", value=260.0, contribution=0.04),
        ],
        vendor=_VENDOR_ACME,
        linked_assets=[
            LinkedAsset(asset_id="AST-1042", description="Cooling Water Pump #1", criticality="HIGH"),
            LinkedAsset(asset_id="AST-1043", description="Cooling Water Pump #2", criticality="HIGH"),
        ],
        audit=_audit_created(),
    ),

    RecommendationDetail(
        rec_id="REC-002", item_id="MOTOR-022",
        item_description="Electric Motor 75kW TEFC", warehouse_id="PERTH/STORE-02",
        type="ROP", criticality="HIGH",
        current_value=8, recommended_value=4,
        delta_working_capital=22_720.0, confidence=0.87,
        status="PENDING", version=1, created_at=_CREATED,
        wc_release=22_720.0, stock_out_risk_change_pct=-0.3,
        model_version="demand-forecast/holt-winters@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="smooth", adi=0.9, cv_squared=0.21,
            twelve_month_mean_qty=36, lead_time_days_mean=21, lead_time_days_std=6,
            service_level_target=0.99,
            summary_text="**Smooth demand** (ADI 0.9, CV² 0.21). Holt-Winters model "
                         "forecasts steady monthly demand. Current ROP of 8 is 4 units "
                         "above the optimal given supplier lead time. Reduction to ROP 4 "
                         "frees ~$22.7k while maintaining the 99% service level.",
        ),
        feature_contributions=[
            FeatureContribution(name="asset_criticality_rollup", value="HIGH", contribution=0.38),
            FeatureContribution(name="unit_cost", value=1_420.0, contribution=0.32),
            FeatureContribution(name="12m_mean_qty", value=36, contribution=0.20),
            FeatureContribution(name="lead_time_mean", value=21, contribution=0.07),
            FeatureContribution(name="on_time_rate", value=0.92, contribution=0.03),
        ],
        vendor=_VENDOR_BETA,
        linked_assets=[
            LinkedAsset(asset_id="AST-2201", description="Conveyor Drive Motor A", criticality="HIGH"),
        ],
        audit=_audit_created([
            AuditEvent(ts=_TS, actor="planner@example.com", event="VIEWED"),
        ]),
    ),

    RecommendationDetail(
        rec_id="REC-003", item_id="VALVE-042",
        item_description="Gate Valve 4\" Class 150", warehouse_id="KALGOOR/STORE-01",
        type="SS", criticality="MED",
        current_value=15, recommended_value=8,
        delta_working_capital=5_600.0, confidence=0.78,
        status="APPROVED", version=2, created_at=_CREATED,
        wc_release=5_600.0, stock_out_risk_change_pct=-0.6,
        model_version="demand-forecast/sbj@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="intermittent", adi=2.1, cv_squared=0.38,
            twelve_month_mean_qty=24, lead_time_days_mean=10, lead_time_days_std=3,
            service_level_target=0.95,
            summary_text="Intermittent demand with moderate variability. "
                         "Safety stock of 15 exceeds the β=0.95 requirement by 7 units. "
                         "Reduction to 8 units releases $5.6k while maintaining the "
                         "95% service-level target for a medium-criticality item.",
        ),
        feature_contributions=[
            FeatureContribution(name="demand_pattern", value="intermittent", contribution=0.35),
            FeatureContribution(name="12m_mean_qty", value=24, contribution=0.28),
            FeatureContribution(name="lead_time_std", value=3, contribution=0.22),
            FeatureContribution(name="unit_cost", value=800.0, contribution=0.15),
        ],
        vendor=VendorInfo(
            vendor_id="V-004", name="Delta Valve Solutions",
            mean_lead_days=10, std_lead_days=3, on_time_pct=0.91,
            unit_cost=800.0, holding_cost_pct=0.20, order_cost=65.0,
        ),
        linked_assets=[
            LinkedAsset(asset_id="AST-3301", description="Process Line Valve Train", criticality="MED"),
        ],
        audit=_audit_created([
            AuditEvent(ts=_TS, actor="mgr@example.com", event="APPROVED",
                       detail="Approved — consistent with Q2 review findings"),
        ]),
    ),

    RecommendationDetail(
        rec_id="REC-004", item_id="BEAR-117",
        item_description="Roller Bearing 6205-2RS", warehouse_id="BEDFORD/STORE-01",
        type="EOQ", criticality="LOW",
        current_value=50, recommended_value=120,
        delta_working_capital=-3_840.0, confidence=0.85,
        status="NEW", version=1, created_at=_CREATED,
        wc_release=-3_840.0, stock_out_risk_change_pct=0.1,
        model_version="optimisation/eoq-wilson@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="smooth", adi=0.6, cv_squared=0.12,
            twelve_month_mean_qty=480, lead_time_days_mean=7, lead_time_days_std=2,
            service_level_target=0.95,
            summary_text="High-volume smooth demand item. Current order quantity of 50 "
                         "generates excess ordering costs. Wilson EOQ formula with "
                         "annual demand 480 units, order cost $55, holding 25% "
                         "yields optimal EOQ of 120 units, reducing total annual "
                         "cost by ~$384 while slightly increasing average stock.",
        ),
        feature_contributions=[
            FeatureContribution(name="annual_demand", value=480, contribution=0.45),
            FeatureContribution(name="order_cost", value=55.0, contribution=0.30),
            FeatureContribution(name="holding_cost_pct", value=0.25, contribution=0.18),
            FeatureContribution(name="unit_cost", value=48.0, contribution=0.07),
        ],
        vendor=_VENDOR_GAMMA,
        linked_assets=[],
        audit=_audit_created(),
    ),

    RecommendationDetail(
        rec_id="REC-005", item_id="SEAL-009",
        item_description="Mechanical Seal Type A", warehouse_id="BEDFORD/STORE-01",
        type="SUB", criticality="MED",
        current_value="SEAL-009", recommended_value="SEAL-012",
        delta_working_capital=4_200.0, confidence=0.74,
        status="NEW", version=1, created_at=_CREATED,
        wc_release=4_200.0, stock_out_risk_change_pct=-0.8,
        model_version="substitution/embedding-v2@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="intermittent", adi=3.2, cv_squared=0.72,
            twelve_month_mean_qty=12, lead_time_days_mean=28, lead_time_days_std=8,
            service_level_target=0.95,
            summary_text="SEAL-009 has intermittent lumpy demand and a 28-day mean "
                         "lead time. SEAL-012 is a pin-compatible substitute with "
                         "14-day lead time and 3× historical stock turns. "
                         "Substitution reduces stock-out risk by ~0.8% while releasing "
                         "$4.2k in slow-moving SEAL-009 inventory.",
        ),
        feature_contributions=[
            FeatureContribution(name="cross_ref_match", value=1, contribution=0.45),
            FeatureContribution(name="embedding_cosine_similarity", value=0.96, contribution=0.25),
            FeatureContribution(name="stock_on_hand_normalised", value=0.82, contribution=0.20),
            FeatureContribution(name="historical_co_use_rate", value=0.12, contribution=0.10),
        ],
        vendor=VendorInfo(
            vendor_id="V-005", name="Epsilon Seals Ltd",
            mean_lead_days=14, std_lead_days=3, on_time_pct=0.94,
            unit_cost=350.0, holding_cost_pct=0.22, order_cost=70.0,
        ),
        linked_assets=[
            LinkedAsset(asset_id="AST-1042", description="Cooling Water Pump #1", criticality="HIGH"),
        ],
        audit=_audit_created(),
    ),

    RecommendationDetail(
        rec_id="REC-006", item_id="PUMP-001",
        item_description="Centrifugal Pump 3\" 15HP", warehouse_id="PERTH/STORE-02",
        type="ROP", criticality="HIGH",
        current_value=20, recommended_value=14,
        delta_working_capital=7_800.0, confidence=0.81,
        status="REJECTED", version=1, created_at=_CREATED,
        wc_release=7_800.0, stock_out_risk_change_pct=-0.2,
        model_version="demand-forecast/sbj@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="intermittent", adi=1.8, cv_squared=0.55,
            twelve_month_mean_qty=60, lead_time_days_mean=14, lead_time_days_std=5,
            service_level_target=0.99,
            summary_text="Intermittent demand at the Perth storeroom. Current ROP of 20 "
                         "is 6 units above optimum for the observed demand and lead time.",
        ),
        feature_contributions=[
            FeatureContribution(name="asset_criticality_rollup", value="HIGH", contribution=0.40),
            FeatureContribution(name="12m_mean_qty", value=60, contribution=0.30),
            FeatureContribution(name="lead_time_std", value=5, contribution=0.20),
            FeatureContribution(name="unit_cost", value=260.0, contribution=0.10),
        ],
        vendor=_VENDOR_ACME,
        linked_assets=[
            LinkedAsset(asset_id="AST-2011", description="Transfer Pump Line 3", criticality="HIGH"),
        ],
        audit=_audit_created([
            AuditEvent(ts=_TS, actor="mgr@example.com", event="REJECTED",
                       detail="Seasonal demand spike expected in Q3 — hold current ROP"),
        ]),
    ),

    RecommendationDetail(
        rec_id="REC-007", item_id="XFMR-007",
        item_description="Distribution Transformer 500kVA", warehouse_id="BEDFORD/STORE-01",
        type="ROP", criticality="HIGH",
        current_value=2, recommended_value=1,
        delta_working_capital=32_500.0, confidence=0.69,
        status="PENDING", version=1, created_at=_CREATED,
        wc_release=32_500.0, stock_out_risk_change_pct=-0.1,
        model_version="demand-forecast/sbj@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="lumpy", adi=4.5, cv_squared=1.2,
            twelve_month_mean_qty=3, lead_time_days_mean=45, lead_time_days_std=14,
            service_level_target=0.995,
            summary_text="**Lumpy demand** — highly infrequent but large-batch usage. "
                         "Long lead time (45 days mean) with high variability. "
                         "Safety-critical classification drives β=0.995. "
                         "Despite this, current ROP of 2 exceeds optimal by 1 unit "
                         "due to improved supplier reliability over the past 12 months.",
        ),
        feature_contributions=[
            FeatureContribution(name="asset_criticality_rollup", value="HIGH", contribution=0.48),
            FeatureContribution(name="lead_time_mean", value=45, contribution=0.28),
            FeatureContribution(name="lead_time_std", value=14, contribution=0.14),
            FeatureContribution(name="on_time_rate", value=0.88, contribution=0.10),
        ],
        vendor=VendorInfo(
            vendor_id="V-006", name="Zeta Power Systems",
            mean_lead_days=45, std_lead_days=14, on_time_pct=0.88,
            unit_cost=32_500.0, holding_cost_pct=0.15, order_cost=250.0,
        ),
        linked_assets=[
            LinkedAsset(asset_id="AST-0501", description="Main Distribution Board #1", criticality="HIGH"),
            LinkedAsset(asset_id="AST-0502", description="Main Distribution Board #2", criticality="HIGH"),
        ],
        audit=_audit_created([
            AuditEvent(ts=_TS, actor="planner@example.com", event="VIEWED"),
        ]),
    ),

    RecommendationDetail(
        rec_id="REC-008", item_id="BELT-203",
        item_description="V-Belt B55 Industrial", warehouse_id="KALGOOR/STORE-01",
        type="WRITEOFF", criticality="LOW",
        current_value=48, recommended_value=0,
        delta_working_capital=4_320.0, confidence=0.91,
        status="APPLIED", version=1, created_at=_CREATED,
        wc_release=4_320.0, stock_out_risk_change_pct=0.0,
        model_version="slow-mover/classifier@2026.05.01", expires_at=_EXPIRES,
        rationale=Rationale(
            demand_pattern="intermittent", adi=6.2, cv_squared=0.08,
            twelve_month_mean_qty=2, lead_time_days_mean=3, lead_time_days_std=1,
            service_level_target=0.95,
            summary_text="48 units on hand with only 2 units consumed in 12 months "
                         "and a 3-day lead time. This item qualifies as a slow-mover "
                         "candidate for write-down or disposal. Release value based "
                         "on current book cost of $90/unit.",
        ),
        feature_contributions=[
            FeatureContribution(name="consumption_velocity", value=2, contribution=0.52),
            FeatureContribution(name="lead_time_mean", value=3, contribution=0.28),
            FeatureContribution(name="on_hand_qty", value=48, contribution=0.15),
            FeatureContribution(name="abc_class", value="C", contribution=0.05),
        ],
        vendor=VendorInfo(
            vendor_id="V-007", name="Eta Drive Components",
            mean_lead_days=3, std_lead_days=1, on_time_pct=0.98,
            unit_cost=90.0, holding_cost_pct=0.25, order_cost=40.0,
        ),
        linked_assets=[],
        audit=_audit_created([
            AuditEvent(ts=_TS, actor="mgr@example.com", event="APPROVED",
                       detail="Write-off approved per quarterly slow-mover review"),
            AuditEvent(ts=_TS, actor="system", event="APPLIED",
                       detail="Written off via MIF OS MXINV_INVENTORY_V1"),
        ]),
    ),
]}


def seed_from_live_data(records: list[dict[str, Any]]) -> int:
    """
    Replace the in-memory store with recommendations generated from live
    MXAPIINVENTORY records.  Always clears the store — including when
    generation produces zero results — so hardcoded seed data is never
    shown when Maximo is reachable.

    Only call this when fetch_inventory succeeded and returned records.
    If Maximo was unreachable, do NOT call this so the seed stays intact.
    """
    from app.recommendations.generator import generate_from_inventory
    live_recs = generate_from_inventory(records)

    # Always replace the store with live results — even if empty.
    # An empty store means "no opportunities found" which is correct.
    _STORE.clear()
    for rec in live_recs:
        _STORE[rec.rec_id] = rec

    if live_recs:
        logger.info("Seeded %d recommendations from live MXAPIINVENTORY data", len(live_recs))
    else:
        logger.info(
            "No recommendations generated from %d inventory records "
            "(no items met the qualifying thresholds) — store is empty",
            len(records),
        )
    return len(live_recs)


def get_all() -> list[RecommendationDetail]:
    return list(_STORE.values())


def get_one(rec_id: str) -> RecommendationDetail | None:
    return _STORE.get(rec_id)


def update_status(
    rec_id: str,
    new_status: str,
    actor: str,
    detail: str | None = None,
) -> RecommendationDetail:
    from datetime import datetime, timezone
    rec = copy.deepcopy(_STORE[rec_id])
    rec.status = new_status  # type: ignore[assignment]
    rec.audit.append(AuditEvent(
        ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        actor=actor,
        event=new_status,  # type: ignore[arg-type]
        detail=detail,
    ))
    _STORE[rec_id] = rec
    return rec


def edit_recommendation(
    rec_id: str,
    recommended_value: float,
    justification: str,
    expected_version: int,
    actor: str,
) -> RecommendationDetail | None:
    """Returns None on version conflict (409)."""
    from datetime import datetime, timezone
    rec = _STORE.get(rec_id)
    if rec is None:
        return None
    if rec.version != expected_version:
        return None   # caller raises 409
    rec = copy.deepcopy(rec)
    rec.recommended_value = recommended_value
    rec.version += 1
    rec.audit.append(AuditEvent(
        ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        actor=actor,
        event="EDITED",
        detail=justification,
    ))
    _STORE[rec_id] = rec
    return rec
