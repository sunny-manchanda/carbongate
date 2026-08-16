# CarbonGate

## Overview
CarbonGate is a Streamlit decision-support tool for CBAM (EU Carbon Border
Adjustment Mechanism) exposure. Users upload an EU import shipment CSV; the app
computes carbon liability per shipment, projects it across the 2026–2034
phase-in, scores supplier data quality, runs a verify-or-abate scenario per
plant, and offers a Groq-backed AI analyst grounded in the computed figures.

## Architecture
- `app.py` — page config (wide), sidebar (EUA price slider 40–150 default 78,
  year selector 2026–2034), tab wiring. The liability pipeline is computed
  **after** the upload tab renders so an upload unlocks the other tabs in the
  same script pass (st.tabs renders all panels in one pass).
- `utils/data_processing.py` — cached reference-table loading, strict upload
  validation (errors name column + row count; file rejected on any error),
  euro formatting (thousands separators, no decimals).
- `utils/cbam_math.py` — calculation chain: covered rows only → join reference
  on cn_code → applicable intensity (reported iff Verified+present, else EU
  default; `intensity_basis` records which) → chargeable = max(applicable −
  benchmark, 0) → gross = chargeable × tonnes × EUA → deduct origin carbon
  price pro-rata to chargeable share, floor at 0 → year liability = net ×
  phase-in factor. Also plant rollups, projection, verify-or-abate scenarios.
- `utils/llm_analyst.py` — Groq client (env: GROQ_API_KEY, GROQ_MODEL), system
  prompt restricts answers to supplied context, disclaimer enforced.
- `components/tab_*.py` — one module per tab (upload, cockpit, quality,
  decision, analyst).
- Reference data from repo root: `cbam_reference_factors.csv`,
  `cbam_phase_in_factors.csv`. Shipments come only via upload.

## Environment
- Run: workflow "Start application" → `streamlit run app.py --server.port 5000`.
- `.streamlit/config.toml`: headless, 0.0.0.0:5000, CORS/XSRF off (required for
  Replit preview iframe). Do not modify.
- `.replit` deployment: VM target, streamlit run command. Direct edits blocked —
  use the dot-replit tools. Do not modify.
- Secrets: GROQ_API_KEY, GROQ_MODEL (set in dev and production). Missing key
  must only disable Tab 5, never crash the app.
- The pnpm artifacts (`artifacts/api-server`, `artifacts/mockup-sandbox`) are
  unrelated scaffolding; the Streamlit app deliberately lives at the repo root.

## User preferences
- Data files deduplicated: canonical CSVs live at repo root, not attached_assets.
- Euro figures always formatted with thousands separators and no decimals.
