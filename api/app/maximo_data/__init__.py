"""
Maximo data fetchers — read-only pulls of the inputs the optimisation
engine and forecasting service need:

    demand.py   — MATUSETRANS issue history per item (monthly buckets).
    leadtime.py — MATRECTRANS receipts joined to PO → lead-time observations.
    vendor.py   — COMPANIES + ITEMORGINFO + INVCOST → vendor block.

All three use the service-account `apikey` header (DLD §6.1) and degrade
gracefully on Maximo errors (return [] / {}) so the orchestrator can decide
how to react.
"""
