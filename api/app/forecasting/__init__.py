"""
Forecasting service — DLD §4.2, §8.

Layout:
    classifier.py — Syntetos/Boylan ADI + CV² demand-pattern classifier.
    service.py    — per-pattern fit/predict, p10/p90 from residuals.
    backtest.py   — rolling-origin CV: WAPE / MAPE / bias per pattern.
"""
