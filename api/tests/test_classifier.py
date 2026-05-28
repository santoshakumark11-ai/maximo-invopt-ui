"""
Unit tests for the Syntetos/Boylan demand-pattern classifier.
Cases cover all four buckets + the no_demand fallback.
"""
from app.forecasting.classifier import classify, _ADI_CUTOFF, _CV2_CUTOFF


def test_smooth_pattern_dense_low_cv():
    # 12 months, all non-zero, similar magnitude → smooth
    series = [10.0, 11, 10, 12, 9, 11, 10, 10, 11, 10, 12, 10]
    r = classify(series)
    assert r.pattern == "smooth"
    assert r.adi < _ADI_CUTOFF
    assert r.cv_squared < _CV2_CUTOFF


def test_intermittent_pattern_sparse_low_cv():
    # 12 months, half zero, similar non-zero magnitudes → intermittent
    series = [10, 0, 10, 0, 11, 0, 10, 0, 9, 0, 10, 0]
    r = classify(series)
    assert r.pattern == "intermittent"
    assert r.adi >= _ADI_CUTOFF
    assert r.cv_squared < _CV2_CUTOFF


def test_erratic_pattern_dense_high_cv():
    # 12 months, all non-zero, but wild variability → erratic
    series = [10, 1, 30, 5, 50, 8, 2, 40, 6, 25, 3, 18]
    r = classify(series)
    assert r.pattern == "erratic"
    assert r.adi < _ADI_CUTOFF
    assert r.cv_squared >= _CV2_CUTOFF


def test_lumpy_pattern_sparse_high_cv():
    # ADI = 12/4 = 3.0  ✓
    # mean of non-zeros = 96.25
    # std (ddof=0) ≈ 95.35
    # CV² ≈ 0.98  → lumpy
    series = [100, 0, 0, 5, 0, 0, 30, 0, 0, 250, 0, 0]
    r = classify(series)
    assert r.pattern == "lumpy"
    assert r.adi >= _ADI_CUTOFF
    assert r.cv_squared >= _CV2_CUTOFF


def test_no_demand_when_zero_or_single_nonzero():
    assert classify([0] * 12).pattern == "no_demand"
    assert classify([5, 0, 0, 0]).pattern == "no_demand"


def test_adi_matches_definition():
    # 4 of 12 periods non-zero ⇒ ADI = 12/4 = 3.0
    series = [0, 5, 0, 5, 0, 5, 0, 5, 0, 0, 0, 0]
    r = classify(series)
    assert abs(r.adi - 3.0) < 1e-9
