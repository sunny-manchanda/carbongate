import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="CBAM Carbon Cost Dashboard",
    page_icon="🌍",
    layout="wide",
)

# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    ships = pd.read_csv("cbam_eu_shipments_2026.csv")
    refs = pd.read_csv("cbam_reference_factors.csv")
    phases = pd.read_csv("cbam_phase_in_factors.csv")
    return ships, refs, phases


ships_raw, refs, phases = load_data()

# ── Sidebar controls ─────────────────────────────────────────────────────────

st.sidebar.title("⚙️ Settings")

ets_price = st.sidebar.slider(
    "EU ETS Carbon Price (€/tCO₂e)",
    min_value=30,
    max_value=150,
    value=65,
    step=5,
    help="Assumed EU ETS price used to value CBAM certificates.",
)

selected_year = st.sidebar.selectbox(
    "Phase-in Year",
    options=phases["year"].tolist(),
    index=0,
)

phase_factor = phases.loc[phases["year"] == selected_year, "cbam_obligation_factor"].values[0]

st.sidebar.markdown(
    f"**Phase-in factor for {selected_year}:** {phase_factor:.1%}"
)
st.sidebar.markdown("---")

# Category / country filters
all_categories = sorted(ships_raw["product_category"].dropna().unique())
sel_categories = st.sidebar.multiselect(
    "Product Category", all_categories, default=all_categories
)

all_countries = sorted(ships_raw["plant_country"].dropna().unique())
sel_countries = st.sidebar.multiselect(
    "Origin Country", all_countries, default=all_countries
)

# ── Calculations ──────────────────────────────────────────────────────────────

def compute_costs(ships: pd.DataFrame, refs: pd.DataFrame, ets: float, factor: float) -> pd.DataFrame:
    df = ships.copy()

    # Only CBAM-covered shipments are subject to CBAM
    df["cbam_covered_flag"] = df["cbam_covered"].str.strip().str.lower() == "yes"

    # Join reference factors for fallback intensity and benchmark
    ref_cols = refs[["cn_code", "eu_default_intensity_tco2e_per_t", "eu_benchmark_intensity_tco2e_per_t"]].copy()
    df = df.merge(ref_cols, on="cn_code", how="left")

    # Reported intensity: use supplier value if present and numeric; else EU default
    rep = pd.to_numeric(df["reported_emissions_intensity_tco2e_per_t"], errors="coerce")
    df["effective_intensity"] = rep.where(rep.notna(), df["eu_default_intensity_tco2e_per_t"])
    df["intensity_source"] = rep.where(rep.notna()).map(lambda x: "Reported" if pd.notna(x) else None)
    df["intensity_source"] = df["intensity_source"].fillna("EU Default")

    # Embedded emissions (tCO₂e)
    df["embedded_emissions_tco2e"] = (
        df["quantity_tonnes"] * df["effective_intensity"]
    ).where(df["cbam_covered_flag"], 0)

    # Carbon price already paid in origin country (EUR) — column is EUR/tCO₂e
    df["carbon_price_paid_eur"] = (
        df["carbon_price_paid_eur_per_t"] * df["embedded_emissions_tco2e"]
    ).fillna(0)

    # Gross CBAM liability before phase-in (EUR)
    df["gross_cbam_eur"] = (
        df["embedded_emissions_tco2e"] * ets - df["carbon_price_paid_eur"]
    ).clip(lower=0).where(df["cbam_covered_flag"], 0)

    # Net CBAM obligation after phase-in (EUR)
    df["net_cbam_obligation_eur"] = df["gross_cbam_eur"] * factor

    # Excess above EU benchmark (tCO₂e) — useful for quality signal
    bench = df["eu_benchmark_intensity_tco2e_per_t"]
    df["intensity_vs_benchmark"] = (df["effective_intensity"] - bench).where(df["cbam_covered_flag"])

    return df


df_all = compute_costs(ships_raw, refs, ets_price, phase_factor)
df = df_all[
    df_all["product_category"].isin(sel_categories) &
    df_all["plant_country"].isin(sel_countries)
].copy()
df_cbam = df[df["cbam_covered_flag"]].copy()

# ── Page header ───────────────────────────────────────────────────────────────

st.title("🌍 CBAM Carbon Cost Dashboard")
st.caption(
    f"EU Carbon Border Adjustment Mechanism · 2026 shipments · "
    f"ETS price €{ets_price}/tCO₂e · Phase-in {phase_factor:.1%} ({selected_year})"
)

# ── KPI cards ─────────────────────────────────────────────────────────────────

total_shipments = len(df)
cbam_shipments = len(df_cbam)
total_embedded = df_cbam["embedded_emissions_tco2e"].sum()
total_net_cbam = df_cbam["net_cbam_obligation_eur"].sum()
total_gross_cbam = df_cbam["gross_cbam_eur"].sum()
total_invoice = df["invoice_value_eur"].sum()
cbam_pct_of_trade = (total_net_cbam / total_invoice * 100) if total_invoice else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Shipments", f"{total_shipments}")
k2.metric("CBAM-Covered", f"{cbam_shipments}", f"{cbam_shipments/total_shipments:.0%} of total")
k3.metric("Embedded Emissions", f"{total_embedded:,.0f} tCO₂e")
k4.metric("Net CBAM Obligation", f"€{total_net_cbam:,.0f}", f"Phase-in {phase_factor:.1%}")
k5.metric("% of Invoice Value", f"{cbam_pct_of_trade:.2f}%", help="Net CBAM as share of total trade value")

st.markdown("---")

# ── Row 1: Cost by product category + by origin country ──────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("CBAM Obligation by Product Category")
    cat_agg = (
        df_cbam.groupby("product_category")
        .agg(net_cbam=("net_cbam_obligation_eur", "sum"), shipments=("shipment_id", "count"))
        .reset_index()
        .sort_values("net_cbam", ascending=False)
    )
    chart = (
        alt.Chart(cat_agg)
        .mark_bar()
        .encode(
            x=alt.X("net_cbam:Q", title="Net CBAM Obligation (€)", axis=alt.Axis(format=",.0f")),
            y=alt.Y("product_category:N", sort="-x", title=""),
            color=alt.Color("product_category:N", legend=None),
            tooltip=[
                alt.Tooltip("product_category:N", title="Category"),
                alt.Tooltip("net_cbam:Q", title="Net CBAM (€)", format=",.0f"),
                alt.Tooltip("shipments:Q", title="Shipments"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)

with col2:
    st.subheader("CBAM Obligation by Origin Country")
    country_agg = (
        df_cbam.groupby("plant_country")
        .agg(net_cbam=("net_cbam_obligation_eur", "sum"), shipments=("shipment_id", "count"))
        .reset_index()
        .sort_values("net_cbam", ascending=False)
    )
    chart2 = (
        alt.Chart(country_agg)
        .mark_bar()
        .encode(
            x=alt.X("net_cbam:Q", title="Net CBAM Obligation (€)", axis=alt.Axis(format=",.0f")),
            y=alt.Y("plant_country:N", sort="-x", title=""),
            color=alt.Color("plant_country:N", legend=None),
            tooltip=[
                alt.Tooltip("plant_country:N", title="Country"),
                alt.Tooltip("net_cbam:Q", title="Net CBAM (€)", format=",.0f"),
                alt.Tooltip("shipments:Q", title="Shipments"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart2, use_container_width=True)

# ── Row 2: Emissions intensity + Phase-in trajectory ─────────────────────────

col3, col4 = st.columns(2)

with col3:
    st.subheader("Reported vs EU Default vs Benchmark Intensity")
    st.caption("Average tCO₂e per tonne by product category (CBAM-covered only)")

    intensity_agg = (
        df_cbam.groupby("product_category")
        .agg(
            reported=("reported_emissions_intensity_tco2e_per_t", lambda x: pd.to_numeric(x, errors="coerce").mean()),
            eu_default=("eu_default_intensity_tco2e_per_t", "mean"),
            benchmark=("eu_benchmark_intensity_tco2e_per_t", "mean"),
        )
        .reset_index()
    )
    intensity_long = intensity_agg.melt(
        id_vars="product_category",
        value_vars=["reported", "eu_default", "benchmark"],
        var_name="intensity_type",
        value_name="intensity",
    )
    label_map = {"reported": "Reported (avg)", "eu_default": "EU Default", "benchmark": "EU Benchmark"}
    intensity_long["intensity_type"] = intensity_long["intensity_type"].map(label_map)

    chart3 = (
        alt.Chart(intensity_long.dropna(subset=["intensity"]))
        .mark_bar()
        .encode(
            x=alt.X("intensity:Q", title="tCO₂e / tonne"),
            y=alt.Y("product_category:N", title=""),
            color=alt.Color(
                "intensity_type:N",
                title="",
                scale=alt.Scale(
                    domain=["Reported (avg)", "EU Default", "EU Benchmark"],
                    range=["#2563eb", "#f59e0b", "#10b981"],
                ),
            ),
            yOffset="intensity_type:N",
            tooltip=[
                alt.Tooltip("product_category:N", title="Category"),
                alt.Tooltip("intensity_type:N", title="Type"),
                alt.Tooltip("intensity:Q", title="tCO₂e/t", format=".3f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart3, use_container_width=True)

with col4:
    st.subheader("Phase-in Trajectory: Projected Annual CBAM Cost")
    st.caption(f"Based on current filtered shipments at €{ets_price}/tCO₂e ETS price")

    gross_total = df_cbam["gross_cbam_eur"].sum()
    phase_proj = phases.copy()
    phase_proj["projected_cbam_eur"] = gross_total * phase_proj["cbam_obligation_factor"]
    phase_proj["year"] = phase_proj["year"].astype(str)
    phase_proj["is_selected"] = phase_proj["year"] == str(selected_year)

    base = alt.Chart(phase_proj).encode(
        x=alt.X("year:O", title="Year"),
        y=alt.Y("projected_cbam_eur:Q", title="Projected CBAM (€)", axis=alt.Axis(format=",.0f")),
        tooltip=[
            alt.Tooltip("year:O", title="Year"),
            alt.Tooltip("cbam_obligation_factor:Q", title="Phase-in Factor", format=".1%"),
            alt.Tooltip("projected_cbam_eur:Q", title="Projected CBAM (€)", format=",.0f"),
        ],
    )
    line = base.mark_line(color="#6366f1", strokeWidth=2)
    points = base.mark_point(filled=True, size=80).encode(
        color=alt.condition(
            alt.datum.is_selected,
            alt.value("#ef4444"),
            alt.value("#6366f1"),
        )
    )
    st.altair_chart((line + points).properties(height=280), use_container_width=True)

# ── Row 3: CBAM by EU importer + data quality ─────────────────────────────────

col5, col6 = st.columns(2)

with col5:
    st.subheader("CBAM Obligation by EU Importer")
    importer_agg = (
        df_cbam.groupby("eu_importer")
        .agg(net_cbam=("net_cbam_obligation_eur", "sum"), shipments=("shipment_id", "count"))
        .reset_index()
        .sort_values("net_cbam", ascending=False)
    )
    chart5 = (
        alt.Chart(importer_agg)
        .mark_bar()
        .encode(
            x=alt.X("net_cbam:Q", title="Net CBAM Obligation (€)", axis=alt.Axis(format=",.0f")),
            y=alt.Y("eu_importer:N", sort="-x", title=""),
            color=alt.Color("eu_importer:N", legend=None),
            tooltip=[
                alt.Tooltip("eu_importer:N", title="EU Importer"),
                alt.Tooltip("net_cbam:Q", title="Net CBAM (€)", format=",.0f"),
                alt.Tooltip("shipments:Q", title="Shipments"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart5, use_container_width=True)

with col6:
    st.subheader("Emissions Data Quality Breakdown")
    st.caption("Shipments where reported intensity was used vs EU default fallback")
    quality_agg = (
        df_cbam.groupby("emissions_data_quality")
        .agg(shipments=("shipment_id", "count"), net_cbam=("net_cbam_obligation_eur", "sum"))
        .reset_index()
        .sort_values("shipments", ascending=False)
    )
    quality_color_map = {
        "Verified": "#10b981",
        "Supplier-reported": "#3b82f6",
        "Estimated": "#f59e0b",
        "Missing": "#ef4444",
        "Not applicable": "#9ca3af",
    }
    quality_agg["color"] = quality_agg["emissions_data_quality"].map(quality_color_map).fillna("#9ca3af")

    chart6 = (
        alt.Chart(quality_agg)
        .mark_bar()
        .encode(
            x=alt.X("shipments:Q", title="Number of Shipments"),
            y=alt.Y("emissions_data_quality:N", sort="-x", title=""),
            color=alt.Color(
                "emissions_data_quality:N",
                legend=None,
                scale=alt.Scale(
                    domain=list(quality_color_map.keys()),
                    range=list(quality_color_map.values()),
                ),
            ),
            tooltip=[
                alt.Tooltip("emissions_data_quality:N", title="Data Quality"),
                alt.Tooltip("shipments:Q", title="Shipments"),
                alt.Tooltip("net_cbam:Q", title="Net CBAM (€)", format=",.0f"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart6, use_container_width=True)

# ── Row 4: Shipment-level scatter ─────────────────────────────────────────────

st.subheader("Shipment-Level: Invoice Value vs CBAM Obligation")
st.caption("Size = quantity (tonnes) · Hover for details · Non-CBAM shipments shown in grey")

scatter_df = df.copy()
scatter_df["cbam_label"] = scatter_df["cbam_covered_flag"].map({True: "CBAM-covered", False: "Not covered"})

scatter = (
    alt.Chart(scatter_df)
    .mark_circle(opacity=0.7)
    .encode(
        x=alt.X("invoice_value_eur:Q", title="Invoice Value (€)", axis=alt.Axis(format=",.0f")),
        y=alt.Y("net_cbam_obligation_eur:Q", title="Net CBAM Obligation (€)", axis=alt.Axis(format=",.0f")),
        size=alt.Size("quantity_tonnes:Q", title="Quantity (t)", scale=alt.Scale(range=[30, 600])),
        color=alt.Color(
            "product_category:N",
            title="Category",
            scale=alt.Scale(scheme="tableau10"),
        ),
        tooltip=[
            alt.Tooltip("shipment_id:O", title="Shipment ID"),
            alt.Tooltip("exporter_entity:N", title="Exporter"),
            alt.Tooltip("plant_country:N", title="Country"),
            alt.Tooltip("product_category:N", title="Category"),
            alt.Tooltip("quantity_tonnes:Q", title="Quantity (t)", format=",.1f"),
            alt.Tooltip("invoice_value_eur:Q", title="Invoice (€)", format=",.0f"),
            alt.Tooltip("effective_intensity:Q", title="Intensity (tCO₂e/t)", format=".3f"),
            alt.Tooltip("intensity_source:N", title="Intensity Source"),
            alt.Tooltip("net_cbam_obligation_eur:Q", title="Net CBAM (€)", format=",.0f"),
        ],
    )
    .properties(height=380)
)
st.altair_chart(scatter, use_container_width=True)

# ── Shipments table ───────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Shipment Detail Table")

show_only_cbam = st.checkbox("Show CBAM-covered shipments only", value=True)
table_df = df_cbam.copy() if show_only_cbam else df.copy()

display_cols = {
    "shipment_id": "ID",
    "invoice_date": "Date",
    "exporter_entity": "Exporter",
    "plant_country": "Country",
    "product_category": "Category",
    "quantity_tonnes": "Qty (t)",
    "invoice_value_eur": "Invoice (€)",
    "effective_intensity": "Intensity (tCO₂e/t)",
    "intensity_source": "Intensity Source",
    "emissions_data_quality": "Data Quality",
    "embedded_emissions_tco2e": "Embedded (tCO₂e)",
    "gross_cbam_eur": "Gross CBAM (€)",
    "net_cbam_obligation_eur": "Net CBAM (€)",
}

table_display = table_df[list(display_cols.keys())].rename(columns=display_cols)

st.dataframe(
    table_display.style.format(
        {
            "Qty (t)": "{:,.1f}",
            "Invoice (€)": "€{:,.0f}",
            "Intensity (tCO₂e/t)": "{:.3f}",
            "Embedded (tCO₂e)": "{:,.1f}",
            "Gross CBAM (€)": "€{:,.0f}",
            "Net CBAM (€)": "€{:,.0f}",
        },
        na_rep="—",
    ),
    use_container_width=True,
    height=400,
)

st.caption(
    "**Methodology:** Embedded emissions = quantity × reported intensity (or EU default where missing). "
    "CBAM obligation = (embedded emissions × ETS price − carbon price already paid) × phase-in factor. "
    "Carbon price credit deducted per tCO₂e of embedded emissions."
)
