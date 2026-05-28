"""
SQLAlchemy ORM models for Q1.1 persistence.

Mapping to DLD §5.2:
    Recommendation            ↔ recommendations
    RecommendationFeature     ↔ recommendation_features
    Approval                  ↔ folded into audit_events
    WritebackAttempt          ↔ writeback_attempts
    AuditEvent (WORM)         ↔ audit_events  (append-only with hash chain)

Plus two Q1.2 additions:
    forecasts                 — persisted ItemForecast snapshots
    forecast_backtests        — per-pattern WAPE / MAPE / bias rolls
    planner_feedback          — captured approve/reject/edit for calibration

Indexes are sized for the reference customer profile in DLD §15.1
(50k items × 20 storerooms).  Postgres handles this without partitioning;
the audit table is partition-ready via the `created_at` column.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

try:
    from sqlalchemy import (
        Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text,
    )
    from sqlalchemy.orm import Mapped, mapped_column, relationship
    _SA_OK = True
except Exception:  # SQLAlchemy not installed
    _SA_OK = False

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


if _SA_OK:

    # ── Recommendations ───────────────────────────────────────────────────────

    class Recommendation(Base):
        __tablename__ = "recommendations"

        rec_id:            Mapped[str]            = mapped_column(String(64), primary_key=True)
        tenant_id:         Mapped[str]            = mapped_column(String(64), default="default", index=True)
        item_id:           Mapped[str]            = mapped_column(String(64), index=True)
        item_description:  Mapped[str]            = mapped_column(String(256), default="")
        warehouse_id:      Mapped[str]            = mapped_column(String(64), index=True)
        type:              Mapped[str]            = mapped_column(String(16))   # ROP|SS|EOQ|SUB|WRITEOFF
        criticality:       Mapped[str]            = mapped_column(String(8))    # HIGH|MED|LOW

        # current_value / recommended_value are unioned float|string at the API
        # boundary (SUB carries an item code).  We persist both representations.
        current_value_num:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        current_value_str:      Mapped[Optional[str]]   = mapped_column(String(64), nullable=True)
        recommended_value_num:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        recommended_value_str:  Mapped[Optional[str]]   = mapped_column(String(64), nullable=True)

        delta_working_capital:     Mapped[float] = mapped_column(Float, default=0.0)
        wc_release:                Mapped[float] = mapped_column(Float, default=0.0)
        stock_out_risk_change_pct: Mapped[float] = mapped_column(Float, default=0.0)

        confidence:        Mapped[float]  = mapped_column(Float, default=0.0)
        status:            Mapped[str]    = mapped_column(String(16), index=True, default="NEW")
        version:           Mapped[int]    = mapped_column(Integer, default=1)
        model_version:     Mapped[str]    = mapped_column(String(64), default="")

        rationale_json:    Mapped[dict]   = mapped_column(JSON, default=dict)
        vendor_json:       Mapped[dict]   = mapped_column(JSON, default=dict)
        linked_assets_json: Mapped[list]  = mapped_column(JSON, default=list)

        created_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
        updated_at:        Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        )
        expires_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True))

        features: Mapped[list["RecommendationFeature"]] = relationship(
            back_populates="recommendation",
            cascade="all, delete-orphan",
        )

        __table_args__ = (
            Index("ix_rec_status_warehouse", "status", "warehouse_id"),
            Index("ix_rec_item_warehouse", "item_id", "warehouse_id"),
        )

    class RecommendationFeature(Base):
        __tablename__ = "recommendation_features"

        id:                Mapped[int]    = mapped_column(Integer, primary_key=True, autoincrement=True)
        rec_id:            Mapped[str]    = mapped_column(
            String(64), ForeignKey("recommendations.rec_id", ondelete="CASCADE"), index=True,
        )
        name:              Mapped[str]    = mapped_column(String(64))
        value_num:         Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        value_str:         Mapped[Optional[str]]   = mapped_column(String(128), nullable=True)
        contribution:      Mapped[float]  = mapped_column(Float, default=0.0)

        recommendation: Mapped["Recommendation"] = relationship(back_populates="features")

    # ── WORM audit log ────────────────────────────────────────────────────────

    class AuditEvent(Base):
        """
        Append-only audit row.  Once written, never updated.  Each row carries:

            prev_hash   = hash of the previous row in the chain (per subject_id)
            row_hash    = HMAC-SHA256(prev_hash || canonical_json(this_row), audit_hmac_secret)
            signature   = same value, stored independently for verification

        See app.audit for write/verify helpers.
        """
        __tablename__ = "audit_events"

        event_id:   Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
        ts:         Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
        tenant_id:  Mapped[str]      = mapped_column(String(64), default="default", index=True)
        principal:  Mapped[str]      = mapped_column(String(128))  # user or "system"
        action:     Mapped[str]      = mapped_column(String(32))   # CREATED|EDITED|APPROVED|REJECTED|APPLIED|FAILED|VIEWED|NOTIFIED
        subject:    Mapped[str]      = mapped_column(String(64), index=True)  # rec_id
        before_state: Mapped[dict]   = mapped_column(JSON, default=dict)
        after_state:  Mapped[dict]   = mapped_column(JSON, default=dict)
        detail:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
        prev_hash:  Mapped[str]      = mapped_column(String(64), default="")  # hex sha256
        row_hash:   Mapped[str]      = mapped_column(String(64), default="")  # hex hmac-sha256

    # ── Writeback attempts ────────────────────────────────────────────────────

    class WritebackAttempt(Base):
        __tablename__ = "writeback_attempts"

        attempt_id: Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
        rec_id:     Mapped[str]      = mapped_column(String(64), index=True)
        target:     Mapped[str]      = mapped_column(String(16))   # MAXIMO|ERP
        status:     Mapped[str]      = mapped_column(String(16))   # PENDING|OK|FAILED|COMPENSATED
        request_payload:  Mapped[dict] = mapped_column(JSON, default=dict)
        response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
        http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
        started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
        ended_at:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
        correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
        error:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Q1.2: forecasting + calibration ───────────────────────────────────────

    class ItemForecast(Base):
        """One snapshot of (mean / p10 / p90) per (item, warehouse, model_version).  Latest wins."""
        __tablename__ = "forecasts"

        id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
        item_id:      Mapped[str]      = mapped_column(String(64), index=True)
        warehouse_id: Mapped[str]      = mapped_column(String(64), index=True)
        model_version: Mapped[str]     = mapped_column(String(64))
        demand_pattern: Mapped[str]    = mapped_column(String(16))   # smooth|intermittent|erratic|lumpy
        adi:          Mapped[float]    = mapped_column(Float, default=0.0)
        cv_squared:   Mapped[float]    = mapped_column(Float, default=0.0)
        history_json:  Mapped[list]    = mapped_column(JSON, default=list)
        forecast_json: Mapped[list]    = mapped_column(JSON, default=list)
        as_of:        Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

        __table_args__ = (
            Index("ix_fc_item_warehouse", "item_id", "warehouse_id"),
        )

    class ForecastBacktest(Base):
        """Aggregated backtest results — one row per (pattern, model_version, run)."""
        __tablename__ = "forecast_backtests"

        id:            Mapped[int]     = mapped_column(Integer, primary_key=True, autoincrement=True)
        run_id:        Mapped[str]     = mapped_column(String(64), index=True)
        pattern:       Mapped[str]     = mapped_column(String(16))
        model_version: Mapped[str]     = mapped_column(String(64))
        n_items:       Mapped[int]     = mapped_column(Integer, default=0)
        wape:          Mapped[float]   = mapped_column(Float, default=0.0)
        mape:          Mapped[float]   = mapped_column(Float, default=0.0)
        bias:          Mapped[float]   = mapped_column(Float, default=0.0)
        as_of:         Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    class PlannerFeedback(Base):
        """
        Calibration capture (Q1.2 shadow mode).  The calibrator model that
        consumes these rows is Q2 work; here we record:
          - the recommendation as planner saw it
          - the planner's decision (approve/reject/edit)
          - the features and raw confidence at decision time

        Used later to train an isotonic / LightGBM calibrator mapping
        (raw confidence, features) → P(approved).
        """
        __tablename__ = "planner_feedback"

        id:            Mapped[int]     = mapped_column(Integer, primary_key=True, autoincrement=True)
        rec_id:        Mapped[str]     = mapped_column(String(64), index=True)
        principal:     Mapped[str]     = mapped_column(String(128))
        decision:      Mapped[str]     = mapped_column(String(16))  # APPROVED|REJECTED|EDITED
        raw_confidence: Mapped[float]  = mapped_column(Float, default=0.0)
        recommended_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        override_value:    Mapped[Optional[float]] = mapped_column(Float, nullable=True)
        reason_or_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
        features_json: Mapped[dict]    = mapped_column(JSON, default=dict)
        decided_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
