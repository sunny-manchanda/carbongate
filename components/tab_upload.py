"""Tab 1 — Shipment Upload: file intake, validation and summary."""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from utils.data_processing import format_eur, summary_stats, validate_shipments


def render() -> None:
    st.subheader("Shipment Upload")
    st.caption(
        "Upload the EU import shipment file (CSV). The file is validated before "
        "any calculation runs; the other tabs unlock once a valid file is loaded."
    )

    uploaded = st.file_uploader(
        "Shipment CSV",
        type=["csv"],
        help="Expected format: one row per shipment with CBAM coverage flags, "
        "quantities, prices and emissions data quality.",
    )

    if uploaded is not None:
        try:
            raw = pd.read_csv(uploaded)
        except Exception as exc:  # noqa: BLE001 — surface parse failures to the user
            st.session_state.pop("shipments", None)
            st.error(f"Could not read the CSV file: {exc}")
            return

        cleaned, errors = validate_shipments(raw)
        if errors:
            st.session_state.pop("shipments", None)
            st.error("The file failed validation and was not loaded:")
            for e in errors:
                st.markdown(f"- {e}")
            return

        token = hashlib.md5(uploaded.getvalue()).hexdigest()
        if st.session_state.get("shipments_token") != token:
            # New dataset — any previous analyst conversation is stale.
            st.session_state.pop("chat_history", None)
        st.session_state["shipments"] = cleaned
        st.session_state["shipments_name"] = uploaded.name
        st.session_state["shipments_token"] = token

    df = st.session_state.get("shipments")
    if df is None:
        st.info("No shipment file loaded yet. Upload a CSV to begin.")
        return

    name = st.session_state.get("shipments_name", "shipment file")
    st.success(f"Validated and loaded **{name}** — {len(df)} rows.")

    stats = summary_stats(df)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Shipments", f"{stats['total_shipments']:,}")
    c2.metric("CBAM-covered", f"{stats['covered_share']:.0%}")
    c3.metric("Total tonnage", f"{stats['total_tonnage']:,.0f} t")
    c4.metric("Invoice value", format_eur(stats["total_invoice_value"]))
    c5.metric("Supplier plants", f"{stats['distinct_plants']:,}")

    if pd.notna(stats["date_min"]) and pd.notna(stats["date_max"]):
        st.caption(
            f"Invoice dates from {stats['date_min']:%d %b %Y} "
            f"to {stats['date_max']:%d %b %Y}."
        )

    st.markdown("##### Cleaned data")
    display = df.copy()
    display["invoice_date"] = display["invoice_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(display, width="stretch", height=420)
