"""Tab 2 — Exposure Cockpit: headline metrics and liability visuals."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_processing import format_eur

_PLOTLY_CONFIG = {"displayModeBar": False}


def render(
    computed: pd.DataFrame,
    shipments: pd.DataFrame,
    projection: pd.DataFrame,
    year: int,
    factor: float,
    eua_price: float,
) -> None:
    st.subheader("Exposure Cockpit")

    if computed.empty:
        st.warning("No CBAM-covered shipments with usable reference factors were found.")
        return

    covered_tonnage = computed["quantity_tonnes"].sum()
    # Invoice value across the WHOLE uploaded book (covered and not) — the
    # denominator a CFO would recognise as EU import revenue exposure.
    invoice_value_all = shipments["invoice_value_eur"].sum()
    net_total = computed["net_liability_eur"].sum()
    year_total = net_total * factor
    pct_of_revenue = (year_total / invoice_value_all) if invoice_value_all else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "CBAM tonnage",
        f"{covered_tonnage:,.0f} t",
        help="Tonnage of CBAM-covered shipments with usable reference factors.",
    )
    c2.metric(
        "EU invoice value (all imports)",
        format_eur(invoice_value_all),
        help="Invoice value of every shipment in the uploaded file, covered or not.",
    )
    c3.metric(f"Liability {year}", format_eur(year_total))
    c4.metric("At full phase-in", format_eur(net_total))
    c5.metric(
        f"% of EU invoice value ({year})",
        f"{pct_of_revenue:.1%}",
        help=f"{year} liability as a share of total uploaded invoice value.",
    )

    st.divider()

    left, right = st.columns((3, 2))

    with left:
        st.markdown(f"##### Liability trajectory 2026–2034 (EUA €{eua_price:,.0f}/t)")
        proj = projection.copy()
        fig = px.line(proj, x="year", y="liability_eur", markers=True)
        fig.add_scatter(
            x=[year],
            y=[year_total],
            mode="markers",
            marker=dict(size=14, color="#d62728", symbol="diamond"),
            name=f"Selected: {year}",
        )
        fig.update_traces(hovertemplate="%{x}: €%{y:,.0f}<extra></extra>")
        fig.update_layout(
            xaxis_title=None,
            yaxis_title="Liability (€)",
            yaxis_tickformat=",.0f",
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            height=380,
        )
        st.plotly_chart(fig, width="stretch", config=_PLOTLY_CONFIG)
        st.caption(
            "Net liability multiplied by the CBAM obligation factor of each year. "
            "The full charge applies from 2034."
        )

    with right:
        st.markdown(f"##### Liability by destination country ({year})")
        by_dest = (
            computed.groupby("destination_country")["net_liability_eur"]
            .sum()
            .mul(factor)
            .sort_values(ascending=True)
            .reset_index()
        )
        fig = px.bar(
            by_dest,
            x="net_liability_eur",
            y="destination_country",
            orientation="h",
        )
        fig.update_traces(
            marker_color="#1f77b4",
            hovertemplate="%{y}: €%{x:,.0f}<extra></extra>",
        )
        fig.update_layout(
            xaxis_title="Liability (€)",
            xaxis_tickformat=",.0f",
            yaxis_title=None,
            margin=dict(l=10, r=10, t=10, b=10),
            height=380,
        )
        st.plotly_chart(fig, width="stretch", config=_PLOTLY_CONFIG)

    st.markdown(f"##### Where the liability sits — product category → supplier plant ({year})")
    tree_data = computed.assign(
        year_liability_eur=computed["net_liability_eur"] * factor
    )
    tree = (
        tree_data.groupby(["product_category", "supplier_plant"])["year_liability_eur"]
        .sum()
        .reset_index()
    )
    tree = tree[tree["year_liability_eur"] > 0]
    if tree.empty:
        st.info(f"No positive liability at the {year} obligation factor.")
        return
    fig = px.treemap(
        tree,
        path=["product_category", "supplier_plant"],
        values="year_liability_eur",
        color="year_liability_eur",
        color_continuous_scale="Reds",
    )
    fig.update_traces(
        hovertemplate="%{label}: €%{value:,.0f}<extra></extra>",
        texttemplate="%{label}<br>€%{value:,.0f}",
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=460,
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, width="stretch", config=_PLOTLY_CONFIG)
