"""Tab 3 — Supplier Data-Quality Heatmap."""

from __future__ import annotations

import pandas as pd
import streamlit as st

TIER_COLORS = {
    "Verified": "#2e7d32",          # green
    "Supplier-reported": "#f9a825",  # amber
    "Estimated": "#ef6c00",          # orange
    "Missing": "#c62828",            # red
}
TIER_TEXT = {
    "Verified": "white",
    "Supplier-reported": "black",
    "Estimated": "white",
    "Missing": "white",
}


def render(plants: pd.DataFrame, year: int) -> None:
    st.subheader("Supplier Data-Quality Heatmap")

    if plants.empty:
        st.warning("No supplier plants to assess.")
        return

    total_tonnage = plants["tonnage"].sum()
    nonverified = plants.loc[plants["data_quality"] != "Verified", "tonnage"].sum()
    nonverified_share = (nonverified / total_tonnage) if total_tonnage else 0.0

    st.metric(
        "CBAM tonnage priced on non-verified data",
        f"{nonverified_share:.0%}",
        help="Share of covered tonnage whose liability rests on EU default values "
        "or unverified supplier figures rather than verified emissions data.",
    )
    if nonverified_share > 0.5:
        st.warning(
            f"{nonverified_share:.0%} of CBAM tonnage is priced on non-verified "
            "data — the liability figures carry material data risk."
        )

    table = plants.sort_values("year_liability_eur", ascending=False).copy()
    table = table[
        [
            "supplier_plant",
            "plant_country",
            "product_category",
            "tonnage",
            "tonnage_share",
            "data_quality",
            "intensity_basis",
            "year_liability_eur",
        ]
    ].rename(
        columns={
            "supplier_plant": "Supplier plant",
            "plant_country": "Country",
            "product_category": "Product",
            "tonnage": "Tonnage (t)",
            "tonnage_share": "Share of tonnage",
            "data_quality": "Data quality",
            "intensity_basis": "Intensity basis",
            "year_liability_eur": f"Liability {year} (€)",
        }
    )

    def tier_style(value: str) -> str:
        color = TIER_COLORS.get(value)
        text = TIER_TEXT.get(value, "black")
        if color:
            return f"background-color: {color}; color: {text}; font-weight: 600;"
        return ""

    styled = (
        table.style.map(tier_style, subset=["Data quality"])
        .format(
            {
                "Tonnage (t)": "{:,.0f}",
                "Share of tonnage": "{:.1%}",
                f"Liability {year} (€)": "€{:,.0f}",
            }
        )
    )
    st.dataframe(styled, width="stretch", height=530, hide_index=True)

    st.caption(
        "Tiers — :green[Verified]: independently verified · "
        ":orange[Supplier-reported]: supplier figure, not verified · "
        ":orange[Estimated]: internal estimate · :red[Missing]: no data, EU default applies. "
        "Sorted by liability contribution."
    )
