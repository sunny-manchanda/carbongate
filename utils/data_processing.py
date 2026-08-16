"""Data loading, validation and summary statistics for CarbonGate."""

from __future__ import annotations

import pandas as pd
import streamlit as st

REFERENCE_FACTORS_PATH = "cbam_reference_factors.csv"
PHASE_IN_FACTORS_PATH = "cbam_phase_in_factors.csv"

# Columns the calculation pipeline requires in an uploaded shipments file.
REQUIRED_COLUMNS = [
    "shipment_id",
    "invoice_date",
    "supplier_plant",
    "plant_country",
    "product_category",
    "cn_code",
    "cbam_covered",
    "quantity_tonnes",
    "unit_price_eur",
    "invoice_value_eur",
    "eu_importer",
    "destination_country",
    "reported_emissions_intensity_tco2e_per_t",
    "emissions_data_quality",
    "carbon_price_paid_eur_per_t",
]

NUMERIC_POSITIVE_COLUMNS = ["quantity_tonnes", "unit_price_eur", "invoice_value_eur"]


@st.cache_data(show_spinner=False)
def load_reference_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the CBAM reference factor and phase-in factor tables from disk."""
    refs = pd.read_csv(REFERENCE_FACTORS_PATH)
    phases = pd.read_csv(PHASE_IN_FACTORS_PATH)
    return refs, phases


def validate_shipments(raw: pd.DataFrame) -> tuple[pd.DataFrame | None, list[str]]:
    """Validate an uploaded shipments dataframe.

    Returns (cleaned_df, errors). cleaned_df is None when validation fails.
    Every error message names the offending column and the number of rows involved.
    """
    errors: list[str] = []

    if raw is None or raw.empty:
        return None, ["The uploaded file contains no data rows."]

    # 1. Required columns present
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        errors.append(
            f"Missing required column(s): {', '.join(missing)}. "
            f"The file has columns: {', '.join(raw.columns)}"
        )
        return None, errors

    df = raw.copy()

    # Normalise string columns used for logic
    for col in ["cbam_covered", "emissions_data_quality", "supplier_plant",
                "plant_country", "product_category", "eu_importer",
                "destination_country"]:
        df[col] = df[col].astype(str).str.strip()

    # 2. Dates parse
    parsed_dates = pd.to_datetime(df["invoice_date"], errors="coerce")
    bad_dates = int(parsed_dates.isna().sum())
    if bad_dates:
        errors.append(
            f"Column 'invoice_date': {bad_dates} row(s) contain dates that cannot be parsed."
        )
    df["invoice_date"] = parsed_dates

    # 3. Quantities and prices are positive
    for col in NUMERIC_POSITIVE_COLUMNS:
        as_num = pd.to_numeric(df[col], errors="coerce")
        non_numeric = int(as_num.isna().sum())
        if non_numeric:
            errors.append(
                f"Column '{col}': {non_numeric} row(s) contain non-numeric values."
            )
        not_positive = int((as_num <= 0).sum())
        if not_positive:
            errors.append(
                f"Column '{col}': {not_positive} row(s) are zero or negative — "
                "quantities and prices must be positive."
            )
        df[col] = as_num

    # 4. cbam_covered contains only Yes/No
    allowed = {"Yes", "No"}
    bad_flag = int((~df["cbam_covered"].isin(allowed)).sum())
    if bad_flag:
        bad_values = sorted(set(df.loc[~df["cbam_covered"].isin(allowed), "cbam_covered"]))
        errors.append(
            f"Column 'cbam_covered': {bad_flag} row(s) contain values other than Yes/No "
            f"(found: {', '.join(map(str, bad_values))})."
        )

    # 5. Optional numeric inputs: blanks are legitimate (e.g. no reported
    # intensity, no origin carbon price) but non-blank garbage or negative
    # values must fail validation, never be silently coerced — silent
    # coercion here would misstate the liability.
    for col, kind in [
        ("reported_emissions_intensity_tco2e_per_t", "emissions intensity"),
        ("carbon_price_paid_eur_per_t", "carbon price"),
    ]:
        original = df[col]
        blank = original.isna() | (original.astype(str).str.strip() == "")
        as_num = pd.to_numeric(original, errors="coerce")
        garbage = int((~blank & as_num.isna()).sum())
        if garbage:
            errors.append(
                f"Column '{col}': {garbage} row(s) contain non-numeric values."
            )
        negative = int((as_num < 0).sum())
        if negative:
            errors.append(
                f"Column '{col}': {negative} row(s) are negative — {kind} "
                "values cannot be negative."
            )
        df[col] = as_num

    df["carbon_price_paid_eur_per_t"] = df["carbon_price_paid_eur_per_t"].fillna(0.0)
    df["cn_code"] = pd.to_numeric(df["cn_code"], errors="coerce").astype("Int64")

    if errors:
        return None, errors
    return df, []


def summary_stats(df: pd.DataFrame) -> dict:
    """Headline statistics for a validated shipments dataframe."""
    covered = df["cbam_covered"] == "Yes"
    return {
        "total_shipments": len(df),
        "covered_share": covered.mean() if len(df) else 0.0,
        "total_tonnage": df["quantity_tonnes"].sum(),
        "total_invoice_value": df["invoice_value_eur"].sum(),
        "distinct_plants": df["supplier_plant"].nunique(),
        "date_min": df["invoice_date"].min(),
        "date_max": df["invoice_date"].max(),
    }


def format_eur(value: float) -> str:
    """Format a value as euros with thousands separators and no decimals."""
    if pd.isna(value):
        return "—"
    return f"€{value:,.0f}"
