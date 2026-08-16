"""CarbonGate — CBAM exposure and decision-support tool.

Five tabs: shipment upload, exposure cockpit, supplier data-quality heatmap,
verify-or-abate decision matrix, and a Groq-backed AI analyst.
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from components import tab_analyst, tab_cockpit, tab_decision, tab_quality, tab_upload
from utils import cbam_math
from utils.data_processing import format_eur, load_reference_tables, summary_stats
from utils.llm_analyst import build_context

load_dotenv()

st.set_page_config(
    page_title="CarbonGate — CBAM Decision Support",
    page_icon="🛃",
    layout="wide",
)

st.title("🛃 CarbonGate")
st.caption(
    "CBAM exposure, data-quality risk and verify-or-abate decisions for EU imports."
)

refs, phases = load_reference_tables()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Assumptions")
    eua_price = st.slider(
        "EUA price (€/tCO₂e)",
        min_value=40,
        max_value=150,
        value=78,
        step=1,
        help="Carbon price used to value chargeable emissions.",
    )
    years = sorted(phases["year"].astype(int).tolist())
    year = st.selectbox(
        "CBAM year",
        options=years,
        index=years.index(2026) if 2026 in years else 0,
        help="Liability is scaled by the phase-in obligation factor of this year.",
    )
    factor = cbam_math.year_factor(phases, int(year))
    st.metric("Obligation factor", f"{factor:.1%}")
    st.caption(
        "Phase-in factors are indicative. Verify against the current CBAM "
        "Implementing Regulation before relying on these figures."
    )

tabs = st.tabs(
    [
        "📤 Shipment Upload",
        "📊 Exposure Cockpit",
        "🌡️ Data-Quality Heatmap",
        "⚖️ Verify-or-Abate",
        "🤖 AI Analyst",
    ]
)

LOCKED_MSG = "Upload a valid shipment file in the **Shipment Upload** tab to unlock this view."

with tabs[0]:
    tab_upload.render()

# ------------------------------------------------------------------ pipeline
# Runs AFTER the upload tab so a file uploaded in this very script run
# unlocks the analysis tabs immediately (st.tabs renders all panels in
# one pass; tab clicks alone do not rerun the script).
shipments = st.session_state.get("shipments")
data_ready = shipments is not None

computed = None
unmatched = None
if data_ready:
    computed, unmatched = cbam_math.compute_row_liability(shipments, refs, eua_price)

with tabs[1]:
    if not data_ready:
        st.info(LOCKED_MSG)
    else:
        if unmatched is not None and not unmatched.empty:
            codes = ", ".join(str(c) for c in sorted(unmatched["cn_code"].dropna().unique()))
            st.warning(
                f"{len(unmatched)} covered shipment row(s) have CN codes missing from "
                f"the reference table ({codes}) and are excluded from the liability."
            )
        projection = cbam_math.liability_projection(computed, phases)
        tab_cockpit.render(
            computed, shipments, projection, int(year), factor, float(eua_price)
        )

with tabs[2]:
    if not data_ready:
        st.info(LOCKED_MSG)
    else:
        plants = cbam_math.plant_rollup(computed, factor)
        tab_quality.render(plants, int(year))

with tabs[3]:
    if not data_ready:
        st.info(LOCKED_MSG)
    else:
        matrix = cbam_math.verify_or_abate(computed, eua_price, factor)
        tab_decision.render(matrix, int(year))

with tabs[4]:
    if not data_ready:
        st.info(LOCKED_MSG)
    else:
        plants = cbam_math.plant_rollup(computed, factor)
        matrix = cbam_math.verify_or_abate(computed, eua_price, factor)
        quality_split = (
            computed.groupby("emissions_data_quality")["quantity_tonnes"]
            .sum()
            .reset_index()
            .rename(columns={"quantity_tonnes": "tonnage"})
        )
        total_t = quality_split["tonnage"].sum()
        quality_split["share"] = quality_split["tonnage"] / total_t if total_t else 0.0
        context = build_context(
            stats=summary_stats(shipments),
            year=int(year),
            factor=factor,
            eua_price=float(eua_price),
            total_net=computed["net_liability_eur"].sum(),
            total_year=computed["net_liability_eur"].sum() * factor,
            plants=plants,
            matrix=matrix,
            quality_split=quality_split,
        )
        tab_analyst.render(context)
