"""
Demand-pattern classifier — DLD §4.2.

Syntetos / Boylan / Croston taxonomy on (ADI, CV²):

    ADI  = mean interval between non-zero demand periods.
    CV²  = squared coefficient of variation of the *non-zero* demand sizes.

Thresholds (DLD §4.2):
    Smooth        : ADI <  1.32  and  CV² <  0.49
    Intermittent  : ADI >= 1.32  and  CV² <  0.49
    Erratic       : ADI <  1.32  and  CV² >= 0.49
    Lumpy         : ADI >= 1.32  and  CV² >= 0.49

NumPy only.  Pure function — easy to unit-test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

try:
    import numpy as np
    _NP = True
except Exception:
    _NP = False

DemandPattern = Literal["smooth", "intermittent", "erratic", "lumpy", "no_demand"]

_ADI_CUTOFF = 1.32
_CV2_CUTOFF = 0.49


@dataclass(frozen=True)
class ClassificationResult:
    pattern: DemandPattern
    adi:     float
    cv_squared: float
    nonzero_periods: int
    total_periods:   int


def classify(series: Iterable[float]) -> ClassificationResult:
    """
    Classify a demand vector (one entry per period, e.g. per month).

    Returns a `ClassificationResult` with ADI, CV², and the chosen pattern.
    `pattern == "no_demand"` is reserved for series with fewer than two
    non-zero observations — there's no statistic to fit on.

    Implementation works even without NumPy (loops in pure Python) so this
    module never blocks the import graph.
    """
    vals = [float(x) for x in series if x is not None]
    n = len(vals)
    nonzero_idx = [i for i, v in enumerate(vals) if v > 0.0]
    k = len(nonzero_idx)

    if n == 0 or k < 2:
        return ClassificationResult(
            pattern="no_demand", adi=float("inf"), cv_squared=float("nan"),
            nonzero_periods=k, total_periods=n,
        )

    # ADI = total periods / non-zero periods (DLD §4.2 statement).
    adi = n / k

    # CV² of non-zero demand sizes.
    sizes = [vals[i] for i in nonzero_idx]
    mean_size = sum(sizes) / k
    if mean_size == 0:
        cv2 = 0.0
    else:
        if _NP:
            arr = np.asarray(sizes, dtype=float)
            std = float(arr.std(ddof=0))  # population std — Syntetos/Boylan use ddof=0
        else:
            var = sum((s - mean_size) ** 2 for s in sizes) / k
            std = var ** 0.5
        cv2 = (std / mean_size) ** 2

    if adi < _ADI_CUTOFF and cv2 < _CV2_CUTOFF:
        pattern: DemandPattern = "smooth"
    elif adi >= _ADI_CUTOFF and cv2 < _CV2_CUTOFF:
        pattern = "intermittent"
    elif adi < _ADI_CUTOFF and cv2 >= _CV2_CUTOFF:
        pattern = "erratic"
    else:
        pattern = "lumpy"

    return ClassificationResult(
        pattern=pattern, adi=adi, cv_squared=cv2,
        nonzero_periods=k, total_periods=n,
    )
