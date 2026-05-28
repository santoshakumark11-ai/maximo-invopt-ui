"""initial schema for Q1.1 persistence + audit + writeback + Q1.2 feedback/backtest

Revision ID: 0001
Revises:
Create Date: 2026-05-26

Creates:
    recommendations, recommendation_features,
    audit_events, writeback_attempts,
    forecasts, forecast_backtests, planner_feedback

The actual column definitions live in app.models_db; this migration uses
op.create_table with the same shape so the schema is reproducible without
relying on autogenerate.  Run autogenerate later for any subsequent change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on:    Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("rec_id",              sa.String(64), primary_key=True),
        sa.Column("tenant_id",           sa.String(64), nullable=False, server_default="default"),
        sa.Column("item_id",             sa.String(64), nullable=False),
        sa.Column("item_description",    sa.String(256), nullable=False, server_default=""),
        sa.Column("warehouse_id",        sa.String(64), nullable=False),
        sa.Column("type",                sa.String(16), nullable=False),
        sa.Column("criticality",         sa.String(8),  nullable=False),
        sa.Column("current_value_num",   sa.Float),
        sa.Column("current_value_str",   sa.String(64)),
        sa.Column("recommended_value_num", sa.Float),
        sa.Column("recommended_value_str", sa.String(64)),
        sa.Column("delta_working_capital",  sa.Float, server_default="0"),
        sa.Column("wc_release",             sa.Float, server_default="0"),
        sa.Column("stock_out_risk_change_pct", sa.Float, server_default="0"),
        sa.Column("confidence",          sa.Float, server_default="0"),
        sa.Column("status",              sa.String(16), nullable=False, server_default="NEW"),
        sa.Column("version",             sa.Integer, nullable=False, server_default="1"),
        sa.Column("model_version",       sa.String(64), server_default=""),
        sa.Column("rationale_json",      sa.JSON, nullable=False),
        sa.Column("vendor_json",         sa.JSON, nullable=False),
        sa.Column("linked_assets_json",  sa.JSON, nullable=False),
        sa.Column("created_at",          sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",          sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at",          sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rec_tenant",           "recommendations", ["tenant_id"])
    op.create_index("ix_rec_item",             "recommendations", ["item_id"])
    op.create_index("ix_rec_warehouse",        "recommendations", ["warehouse_id"])
    op.create_index("ix_rec_status",           "recommendations", ["status"])
    op.create_index("ix_rec_status_warehouse", "recommendations", ["status", "warehouse_id"])
    op.create_index("ix_rec_item_warehouse",   "recommendations", ["item_id", "warehouse_id"])

    op.create_table(
        "recommendation_features",
        sa.Column("id",        sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rec_id",    sa.String(64), sa.ForeignKey("recommendations.rec_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name",      sa.String(64), nullable=False),
        sa.Column("value_num", sa.Float),
        sa.Column("value_str", sa.String(128)),
        sa.Column("contribution", sa.Float, server_default="0"),
    )
    op.create_index("ix_recfeat_rec", "recommendation_features", ["rec_id"])

    op.create_table(
        "audit_events",
        sa.Column("event_id",     sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts",           sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id",    sa.String(64), nullable=False, server_default="default"),
        sa.Column("principal",    sa.String(128), nullable=False),
        sa.Column("action",       sa.String(32), nullable=False),
        sa.Column("subject",      sa.String(64), nullable=False),
        sa.Column("before_state", sa.JSON,  nullable=False),
        sa.Column("after_state",  sa.JSON,  nullable=False),
        sa.Column("detail",       sa.Text),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("prev_hash",    sa.String(64), nullable=False, server_default=""),
        sa.Column("row_hash",     sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_audit_ts",       "audit_events", ["ts"])
    op.create_index("ix_audit_tenant",   "audit_events", ["tenant_id"])
    op.create_index("ix_audit_subject",  "audit_events", ["subject"])

    op.create_table(
        "writeback_attempts",
        sa.Column("attempt_id",   sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rec_id",       sa.String(64), nullable=False),
        sa.Column("target",       sa.String(16), nullable=False),
        sa.Column("status",       sa.String(16), nullable=False),
        sa.Column("request_payload",  sa.JSON, nullable=False),
        sa.Column("response_payload", sa.JSON, nullable=False),
        sa.Column("http_status",  sa.Integer),
        sa.Column("started_at",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at",     sa.DateTime(timezone=True)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("error",        sa.Text),
    )
    op.create_index("ix_wb_rec", "writeback_attempts", ["rec_id"])

    op.create_table(
        "forecasts",
        sa.Column("id",            sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_id",       sa.String(64), nullable=False),
        sa.Column("warehouse_id",  sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("demand_pattern", sa.String(16), nullable=False),
        sa.Column("adi",           sa.Float, server_default="0"),
        sa.Column("cv_squared",    sa.Float, server_default="0"),
        sa.Column("history_json",  sa.JSON, nullable=False),
        sa.Column("forecast_json", sa.JSON, nullable=False),
        sa.Column("as_of",         sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fc_item",       "forecasts", ["item_id"])
    op.create_index("ix_fc_warehouse",  "forecasts", ["warehouse_id"])
    op.create_index("ix_fc_item_warehouse", "forecasts", ["item_id", "warehouse_id"])

    op.create_table(
        "forecast_backtests",
        sa.Column("id",            sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id",        sa.String(64), nullable=False),
        sa.Column("pattern",       sa.String(16), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("n_items",       sa.Integer, nullable=False, server_default="0"),
        sa.Column("wape",          sa.Float,   nullable=False, server_default="0"),
        sa.Column("mape",          sa.Float,   nullable=False, server_default="0"),
        sa.Column("bias",          sa.Float,   nullable=False, server_default="0"),
        sa.Column("as_of",         sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bt_run", "forecast_backtests", ["run_id"])

    op.create_table(
        "planner_feedback",
        sa.Column("id",                sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rec_id",            sa.String(64), nullable=False),
        sa.Column("principal",         sa.String(128), nullable=False),
        sa.Column("decision",          sa.String(16), nullable=False),
        sa.Column("raw_confidence",    sa.Float, server_default="0"),
        sa.Column("recommended_value", sa.Float),
        sa.Column("override_value",    sa.Float),
        sa.Column("reason_or_justification", sa.Text),
        sa.Column("features_json",     sa.JSON, nullable=False),
        sa.Column("decided_at",        sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fb_rec", "planner_feedback", ["rec_id"])


def downgrade() -> None:
    op.drop_table("planner_feedback")
    op.drop_table("forecast_backtests")
    op.drop_table("forecasts")
    op.drop_table("writeback_attempts")
    op.drop_table("audit_events")
    op.drop_table("recommendation_features")
    op.drop_table("recommendations")
