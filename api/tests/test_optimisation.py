"""
Unit tests for the optimisation engine (DLD §8.1, §8.3).
"""
import math

from app.optimisation.engine import (
    OptimisationInput, beta_for, compute_eoq, compute_recommendation,
    _normal_ss_rop, _wilson_eoq,
)


def test_beta_routing_by_criticality():
    assert beta_for("HIGH")  >= beta_for("MED")
    assert beta_for("MED")   >= beta_for("LOW")


def test_normal_ss_rop_matches_dld_appendix_b_within_rounding():
    # DLD Appendix B worked example:
    #   μ_d=7 units/month, σ_d=4, μ_L=0.46mo, σ_L=0.13mo, β=0.99 → SS≈7, ROP≈11
    ss, rop = _normal_ss_rop(
        beta=0.99, mu_d=7, sigma_d=4, mu_l=0.46, sigma_l=0.13,
    )
    # Allow a unit of slack for table-vs-scipy z-score rounding.
    assert math.ceil(ss)  in (6, 7, 8)
    assert math.ceil(rop) in (10, 11, 12)


def test_normal_ss_grows_with_service_level():
    # Tighter β ⇒ larger SS.
    ss95, _ = _normal_ss_rop(beta=0.95, mu_d=5, sigma_d=2, mu_l=1, sigma_l=0.5)
    ss99, _ = _normal_ss_rop(beta=0.99, mu_d=5, sigma_d=2, mu_l=1, sigma_l=0.5)
    assert ss99 > ss95


def test_wilson_eoq_closed_form():
    # D=12000/yr, K=$75, h=$2/unit/yr ⇒ EOQ = sqrt(2·D·K/h)
    q = _wilson_eoq(annual_demand=12_000, order_cost=75.0, unit_holding_cost=2.0)
    assert abs(q - math.sqrt(2 * 12_000 * 75 / 2)) < 1e-6


def test_eoq_handles_discount_breaks():
    # Cheaper price kicks in at q≥500, evaluate TC against unbroken Wilson.
    q_no_break = compute_eoq(annual_demand=10_000, unit_cost=10.0,
                             order_cost=50.0, holding_cost_pct=0.2,
                             price_breaks=[])
    q_with_break = compute_eoq(annual_demand=10_000, unit_cost=10.0,
                               order_cost=50.0, holding_cost_pct=0.2,
                               price_breaks=[(500, 9.0)])
    # The discount should never make EOQ less attractive.
    assert q_with_break >= q_no_break - 1e-6


def test_compute_recommendation_smoke():
    """End-to-end smoke test on a small intermittent series."""
    inp = OptimisationInput(
        item_id="X", warehouse_id="W", criticality="HIGH",
        demand_history=[10, 0, 12, 0, 8, 0, 11, 0, 9, 0, 10, 0,
                        12, 0, 8, 0, 10, 0, 9, 0, 11, 0, 12, 0],
        lead_time_days=[14, 12, 16, 13, 15, 14],
        unit_cost=260.0, order_cost=75.0, holding_cost_pct=0.22,
        current_rop=32,
    )
    res = compute_recommendation(inp)
    assert res.rop >= 0
    assert res.ss  >= 0
    assert res.eoq >= 0
    assert res.beta == beta_for("HIGH")
