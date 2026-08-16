"""CBAM liability mathematics for CarbonGate.

Implements the exact calculation chain:

1. Keep only rows where cbam_covered == "Yes"; join reference factors on cn_code.
2. applicable_intensity = reported intensity when emissions_data_quality is
   "Verified" and a reported value exists, otherwise the EU default.
   intensity_basis records which was used.
3. chargeable_intensity = max(applicable_intensity - eu_benchmark_intensity, 0)
4. gross_liability_eur = chargeable_intensity * quantity_tonnes * eua_price
5. Deduct carbon price already paid at origin:
   deduction = carbon_price_paid_eur_per_t * quantity_tonnes
               * chargeable_intensity / applicable_intensity, net floored at zero.
6. year_liability = net_liability * cbam_obligation_factor for the chosen year.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASIS_REPORTED = "Reported (verified)"
BASIS_DEFAULT = "EU default"

QUALITY_ORDER = ["Verified", "Supplier-reported", "Estimated", "Missing"]


def compute_row_liability(
    shipments: pd.DataFrame,
    refs: pd.DataFrame,
    eua_price: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-row CBAM liability for covered shipments.

    Returns (computed, unmatched) where `unmatched` contains covered rows whose
    cn_code is missing from the reference table (excluded from liability).
    """
    covered = shipments[shipments["cbam_covered"] == "Yes"].copy()

    ref_cols = refs[
        ["cn_code", "product_group", "eu_default_intensity_tco2e_per_t",
         "eu_benchmark_intensity_tco2e_per_t"]
    ].copy()
    ref_cols["cn_code"] = pd.to_numeric(ref_cols["cn_code"], errors="coerce").astype("Int64")

    df = covered.merge(ref_cols, on="cn_code", how="left")

    # CN codes missing from the reference table cannot be priced — split them out.
    unmatched = df[df["eu_default_intensity_tco2e_per_t"].isna()].copy()
    df = df[df["eu_default_intensity_tco2e_per_t"].notna()].copy()

    if df.empty:
        return df, unmatched

    reported = df["reported_emissions_intensity_tco2e_per_t"]
    is_verified = df["emissions_data_quality"] == "Verified"
    use_reported = is_verified & reported.notna()

    df["applicable_intensity"] = np.where(
        use_reported, reported, df["eu_default_intensity_tco2e_per_t"]
    )
    df["intensity_basis"] = np.where(use_reported, BASIS_REPORTED, BASIS_DEFAULT)

    df["chargeable_intensity"] = (
        df["applicable_intensity"] - df["eu_benchmark_intensity_tco2e_per_t"]
    ).clip(lower=0)

    df["gross_liability_eur"] = (
        df["chargeable_intensity"] * df["quantity_tonnes"] * eua_price
    )

    # Carbon price paid at origin, scaled to the chargeable share of intensity.
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(
            df["applicable_intensity"] > 0,
            df["chargeable_intensity"] / df["applicable_intensity"],
            0.0,
        )
    df["origin_carbon_deduction_eur"] = (
        df["carbon_price_paid_eur_per_t"] * df["quantity_tonnes"] * share
    )

    df["net_liability_eur"] = (
        df["gross_liability_eur"] - df["origin_carbon_deduction_eur"]
    ).clip(lower=0)

    return df, unmatched


def year_factor(phases: pd.DataFrame, year: int) -> float:
    """Look up the CBAM obligation factor for a given year."""
    row = phases.loc[phases["year"] == year, "cbam_obligation_factor"]
    return float(row.iloc[0]) if len(row) else 1.0


def liability_projection(computed: pd.DataFrame, phases: pd.DataFrame) -> pd.DataFrame:
    """Total liability for each phase-in year (net liability x factor)."""
    net_total = computed["net_liability_eur"].sum() if len(computed) else 0.0
    proj = phases.copy()
    proj["liability_eur"] = net_total * proj["cbam_obligation_factor"]
    return proj


def plant_rollup(computed: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Aggregate computed rows to one row per supplier plant."""
    if computed.empty:
        return pd.DataFrame()

    def dominant(series: pd.Series) -> str:
        return series.mode().iloc[0] if len(series) else ""

    grouped = (
        computed.groupby("supplier_plant")
        .agg(
            plant_country=("plant_country", dominant),
            product_category=("product_category", dominant),
            tonnage=("quantity_tonnes", "sum"),
            data_quality=("emissions_data_quality", dominant),
            intensity_basis=("intensity_basis", dominant),
            net_liability_eur=("net_liability_eur", "sum"),
        )
        .reset_index()
    )
    total_tonnage = grouped["tonnage"].sum()
    grouped["tonnage_share"] = np.where(
        total_tonnage > 0, grouped["tonnage"] / total_tonnage, 0.0
    )
    grouped["year_liability_eur"] = grouped["net_liability_eur"] * factor
    return grouped.sort_values("year_liability_eur", ascending=False)


def _net_liability_for_intensity(
    rows: pd.DataFrame, intensity: pd.Series, eua_price: float
) -> pd.Series:
    """Net liability per row when a given applicable intensity is assumed."""
    chargeable = (intensity - rows["eu_benchmark_intensity_tco2e_per_t"]).clip(lower=0)
    gross = chargeable * rows["quantity_tonnes"] * eua_price
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(intensity > 0, chargeable / intensity, 0.0)
    deduction = rows["carbon_price_paid_eur_per_t"] * rows["quantity_tonnes"] * share
    return (gross - deduction).clip(lower=0)


def verify_or_abate(
    computed: pd.DataFrame, eua_price: float, factor: float
) -> pd.DataFrame:
    """Per-plant comparison of liability on the EU default basis vs the
    liability if the plant's reported intensity were verified.

    Only plants currently on a non-verified basis are assessed. Plants with no
    reported intensity at all cannot be compared and receive the action
    "Obtain emissions data".
    """
    nonverified = computed[computed["intensity_basis"] == BASIS_DEFAULT].copy()
    if nonverified.empty:
        return pd.DataFrame()

    # Scenario A — stay on EU default values (current position for these rows).
    nonverified["liability_default"] = _net_liability_for_intensity(
        nonverified, nonverified["eu_default_intensity_tco2e_per_t"], eua_price
    )
    # Scenario B — reported intensity becomes verified (only where reported exists).
    reported = nonverified["reported_emissions_intensity_tco2e_per_t"]
    liability_reported = _net_liability_for_intensity(nonverified, reported, eua_price)
    nonverified["liability_verified"] = np.where(
        reported.notna(), liability_reported, np.nan
    )

    def dominant(series: pd.Series) -> str:
        return series.mode().iloc[0] if len(series) else ""

    plants = (
        nonverified.groupby("supplier_plant")
        .agg(
            plant_country=("plant_country", dominant),
            product_category=("product_category", dominant),
            tonnage=("quantity_tonnes", "sum"),
            data_quality=("emissions_data_quality", dominant),
            liability_default=("liability_default", "sum"),
            liability_verified=("liability_verified", "sum"),
            has_reported=("reported_emissions_intensity_tco2e_per_t", lambda s: s.notna().all()),
        )
        .reset_index()
    )

    plants["liability_default"] *= factor
    plants["liability_verified"] = np.where(
        plants["has_reported"], plants["liability_verified"] * factor, np.nan
    )

    # delta < 0 → verification lowers the bill (upside);
    # delta > 0 → reported is worse than default (hidden liability).
    plants["delta_eur"] = plants["liability_verified"] - plants["liability_default"]

    def action(row: pd.Series) -> str:
        if not row["has_reported"]:
            return "Obtain emissions data"
        if row["delta_eur"] < 0:
            return "Verify emissions data"
        if row["delta_eur"] > 0:
            return "Abate or re-source"
        return "Monitor"

    plants["recommended_action"] = plants.apply(action, axis=1)
    plants["group"] = np.select(
        [
            ~plants["has_reported"],
            plants["delta_eur"] < 0,
            plants["delta_eur"] > 0,
        ],
        ["No data", "Verification upside", "Hidden liability"],
        default="Neutral",
    )
    return plants.sort_values("delta_eur", na_position="last")
