"""Tab 4 — Verify-or-Abate Decision Matrix."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_processing import format_eur

GROUP_COLORS = {
    "Verification upside": "#2e7d32",
    "Hidden liability": "#c62828",
    "No data": "#9e9e9e",
    "Neutral": "#607d8b",
}

_PLOTLY_CONFIG = {"displayModeBar": False}


def render(matrix: pd.DataFrame, year: int) -> None:
    st.subheader("Verify-or-Abate Decision Matrix")
    st.caption(
        "For every plant currently priced on EU default values: what would the "
        f"{year} liability be if its reported intensity were verified? "
        "Negative delta = verification lowers the bill. Positive delta = the "
        "reported figure is worse than the default — verification would raise it."
    )

    if matrix is None or matrix.empty:
        st.success("Every plant is already priced on verified data — nothing to assess.")
        return

    upside = matrix[matrix["group"] == "Verification upside"]
    hidden = matrix[matrix["group"] == "Hidden liability"]
    nodata = matrix[matrix["group"] == "No data"]

    net_delta = matrix["delta_eur"].sum(skipna=True)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Verification upside",
        format_eur(-upside["delta_eur"].sum()) if len(upside) else "€0",
        help="Total annual saving available by verifying plants whose reported "
        "intensity beats the EU default.",
    )
    c2.metric(
        "Hidden liability",
        format_eur(hidden["delta_eur"].sum()) if len(hidden) else "€0",
        help="Liability increase that verification would expose at plants whose "
        "reported intensity is worse than the EU default.",
    )
    c3.metric(
        "Net portfolio position",
        format_eur(net_delta),
        delta=("saving" if net_delta < 0 else "increase") if net_delta else None,
        delta_color="inverse" if net_delta else "off",
        help="Change in liability if every plant with reported data were verified.",
    )

    if not hidden.empty:
        names = ", ".join(hidden["supplier_plant"])
        st.error(
            f"⚠️ Hidden liability: **{names}** report emissions intensities *above* "
            "the EU default. Verifying their data would **increase** the CBAM bill — "
            "the correct lever here is **abatement or re-sourcing, not data collection**."
        )

    plotted = matrix[matrix["delta_eur"].notna()].sort_values("delta_eur")
    if not plotted.empty:
        st.markdown(f"##### Liability change if reported intensity were verified ({year}, €)")
        fig = go.Figure(
            go.Bar(
                x=plotted["delta_eur"],
                y=plotted["supplier_plant"],
                orientation="h",
                marker_color=[GROUP_COLORS[g] for g in plotted["group"]],
                hovertemplate="%{y}: €%{x:,.0f}<extra></extra>",
            )
        )
        fig.add_vline(x=0, line_width=2, line_color="#37474f")
        fig.update_layout(
            xaxis_title="Δ liability (€) — negative is a saving",
            xaxis_tickformat=",.0f",
            yaxis_title=None,
            margin=dict(l=10, r=10, t=10, b=10),
            height=max(300, 60 * len(plotted)),
        )
        st.plotly_chart(fig, width="stretch", config=_PLOTLY_CONFIG)

    st.markdown("##### Ranked action table")
    table = matrix.copy().sort_values("delta_eur", na_position="last")
    table = table[
        [
            "supplier_plant",
            "plant_country",
            "product_category",
            "tonnage",
            "data_quality",
            "liability_default",
            "liability_verified",
            "delta_eur",
            "recommended_action",
        ]
    ].rename(
        columns={
            "supplier_plant": "Supplier plant",
            "plant_country": "Country",
            "product_category": "Product",
            "tonnage": "Tonnage (t)",
            "data_quality": "Data quality",
            "liability_default": f"On EU default {year} (€)",
            "liability_verified": f"If verified {year} (€)",
            "delta_eur": "Δ (€)",
            "recommended_action": "Recommended action",
        }
    )

    def action_style(value: str) -> str:
        styles = {
            "Verify emissions data": "color: #2e7d32; font-weight: 600;",
            "Abate or re-source": "color: #c62828; font-weight: 700;",
            "Obtain emissions data": "color: #616161; font-weight: 600;",
        }
        return styles.get(value, "")

    styled = table.style.map(action_style, subset=["Recommended action"]).format(
        {
            "Tonnage (t)": "{:,.0f}",
            f"On EU default {year} (€)": "€{:,.0f}",
            f"If verified {year} (€)": lambda v: "—" if pd.isna(v) else f"€{v:,.0f}",
            "Δ (€)": lambda v: "—" if pd.isna(v) else f"€{v:,.0f}",
        }
    )
    st.dataframe(styled, width="stretch", hide_index=True)

    if not nodata.empty:
        st.caption(
            f"{len(nodata)} plant(s) have no reported intensity at all and are "
            "priced on EU defaults; obtaining any emissions data is the first step "
            "before a verify-or-abate call can be made."
        )
