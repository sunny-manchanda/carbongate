# CarbonGate

CBAM (EU Carbon Border Adjustment Mechanism) exposure and decision-support
tool for procurement and finance teams importing CBAM-covered goods into the EU.

## What it does

1. **Shipment Upload** — upload the EU import shipment CSV; the file is
   validated (columns, positive quantities/prices, parseable dates, Yes/No
   coverage flags) before anything is calculated.
2. **Exposure Cockpit** — headline liability metrics, the 2026–2034 phase-in
   trajectory, a treemap of liability by product category → supplier plant,
   and liability by destination country.
3. **Supplier Data-Quality Heatmap** — one row per plant with tonnage,
   quality tier (Verified / Supplier-reported / Estimated / Missing) and the
   intensity basis used, plus the share of tonnage priced on non-verified data.
4. **Verify-or-Abate Decision Matrix** — for every non-verified plant, the
   liability on EU default values vs the liability if its reported intensity
   were verified: verification upside vs hidden liability, with a ranked
   action table.
5. **AI Analyst** — Groq-powered chat grounded strictly in the computed
   figures, with one-click presets for a supplier data-request email and a
   150-word board summary.

## Calculation methodology

- Only `cbam_covered == "Yes"` rows are priced; reference factors join on `cn_code`.
- Applicable intensity = reported value when `emissions_data_quality == "Verified"`
  and a value exists, otherwise the EU default (`intensity_basis` records which).
- Chargeable intensity = `max(applicable − EU benchmark, 0)`.
- Gross liability = chargeable intensity × tonnes × EUA price (sidebar slider,
  default €78, range €40–150).
- Carbon prices already paid at origin are deducted pro-rata to the chargeable
  share of intensity; net liability is floored at zero.
- The selected year's liability = net liability × that year's CBAM obligation
  factor (2.5 % in 2026 rising to 100 % by 2034).

Phase-in factors are indicative — verify against the current CBAM Implementing
Regulation.

## Project structure

```
app.py                    # layout, sidebar, tab wiring
utils/
  data_processing.py      # reference loading (cached), validation, formatting
  cbam_math.py            # liability chain, rollups, verify-or-abate scenarios
  llm_analyst.py          # Groq client, grounded prompt, presets
components/
  tab_upload.py           # Tab 1
  tab_cockpit.py          # Tab 2
  tab_quality.py          # Tab 3
  tab_decision.py         # Tab 4
  tab_analyst.py          # Tab 5
cbam_reference_factors.csv    # CN-code default/benchmark intensities (from disk)
cbam_phase_in_factors.csv     # 2026–2034 obligation factors (from disk)
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Enables the AI Analyst tab. App runs without it; only Tab 5 is disabled. |
| `GROQ_MODEL` | Groq model name used for analysis. |

## Running

```bash
streamlit run app.py --server.port 5000
```

The app is served on port 5000 (`.streamlit/config.toml` sets headless mode and
binds 0.0.0.0 for the Replit preview).
