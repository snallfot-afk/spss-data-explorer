"""SPSS Data Explorer — Streamlit app."""

from __future__ import annotations

import os
import tempfile
import traceback

import numpy as np
import pandas as pd
import pyreadstat
import streamlit as st

st.set_page_config(page_title="SPSS Data Explorer", layout="wide")


# ── helpers ──────────────────────────────────────────────────────────────────

def read_sav(path: str):
    try:
        return pyreadstat.read_sav(path, apply_value_formats=False)
    except UnicodeDecodeError:
        return pyreadstat.read_sav(path, apply_value_formats=False, encoding="LATIN1")


def value_labels_map(meta) -> dict[str, dict]:
    out: dict[str, dict] = {}
    var_to_set = getattr(meta, "variable_to_label", {}) or {}
    label_sets = getattr(meta, "value_labels", {}) or {}
    for var, set_name in var_to_set.items():
        labels = label_sets.get(set_name)
        if labels:
            out[var] = {str(k): v for k, v in labels.items()}
    return out


def column_header(varname: str, column_labels: dict[str, str]) -> str:
    label = column_labels.get(varname)
    if label and label != varname:
        return f"{label} ({varname})"
    return varname


def labeled_series(df: pd.DataFrame, var: str, value_labels: dict) -> pd.Series:
    s = df[var]
    labels = value_labels.get(var)
    if labels:
        def _map(v):
            if pd.isna(v):
                return None
            key = str(int(v)) if isinstance(v, (int, float, np.integer, np.floating)) and float(v) == int(v) else str(v)
            return labels.get(key, labels.get(str(v), str(v)))
        return s.map(_map)
    return s.where(s.notna(), None).astype(object).map(lambda v: None if v is None else str(v))


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🗂 SPSS Data Explorer")
    st.markdown("""
Upload an SPSS `.sav` file to:
1. **Browse** data in a table
2. **Download** as CSV
3. **Crosstab** any two variables
""")


# ── upload (no session state, direct flow) ───────────────────────────────────

st.header("Upload a .sav file")
uploaded = st.file_uploader("Choose a .sav file", type=["sav"], key="sav_uploader")

if uploaded is None:
    st.info("Upload a .sav file to get started. Try `python generate_sample.py` for a test file.")
    st.stop()

# Process file immediately without caching in session_state
with st.spinner(f"Reading {uploaded.name}…"):
    try:
        file_bytes = uploaded.getvalue()  # Use getvalue() instead of read()
        
        with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        df, meta = read_sav(tmp_path)
        os.unlink(tmp_path)

        column_labels = {
            name: lbl
            for name, lbl in zip(meta.column_names, meta.column_labels or [])
            if lbl
        }
        value_labels = value_labels_map(meta)
        filename = uploaded.name

    except Exception as exc:
        st.error(f"❌ Failed to read file: {exc}")
        st.code(traceback.format_exc())
        st.stop()

# ── data loaded — show everything ────────────────────────────────────────────

rows, cols = df.shape
labeled_count = sum(1 for c in df.columns if c in column_labels)

# Metrics row
c1, c2, c3, c4 = st.columns(4)
c1.metric("File", filename)
c2.metric("Rows", f"{rows:,}")
c3.metric("Columns", f"{cols:,}")
c4.metric("Labeled vars", f"{labeled_count}/{cols}")

st.divider()

# ── tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["📊 Data Browser", "🔢 Crosstab"])

with tab1:
    header_map = {c: column_header(c, column_labels) for c in df.columns}
    display_df = df.rename(columns=header_map)
    st.dataframe(display_df, use_container_width=True, height=500)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv_bytes,
        file_name=os.path.splitext(filename)[0] + ".csv",
        mime="text/csv",
    )

with tab2:
    var_options = list(df.columns)
    def _fmt(v): return column_header(v, column_labels)

    col_a, col_b = st.columns(2)
    row_var = col_a.selectbox("Row variable", var_options, format_func=_fmt)
    col_var = col_b.selectbox("Column variable", var_options, index=min(1, len(var_options) - 1), format_func=_fmt)

    if st.button("Generate crosstab", type="primary"):
        if row_var == col_var:
            st.warning("Pick two different variables.")
        else:
            r = labeled_series(df, row_var, value_labels)
            c = labeled_series(df, col_var, value_labels)
            work = pd.DataFrame({"r": r, "c": c}).dropna()
            if work.empty:
                st.warning("No non-missing data for this pair.")
            else:
                counts = pd.crosstab(work["r"], work["c"])
                row_totals = counts.sum(axis=1)
                col_totals = counts.sum(axis=0)
                grand_total = int(counts.values.sum())

                counts_out = counts.copy()
                counts_out["Total"] = row_totals
                totals_row = pd.Series({c: int(col_totals[c]) for c in counts.columns}, name="Total")
                totals_row["Total"] = grand_total
                counts_out = pd.concat([counts_out, totals_row.to_frame().T])

                row_pct = counts.div(row_totals.replace(0, np.nan), axis=0).mul(100).fillna(0).round(1)

                st.markdown(f"*Counts* — rows: **{_fmt(row_var)}**, columns: **{_fmt(col_var)}**")
                st.dataframe(counts_out, use_container_width=True)

                st.markdown("*Row percentages (%)*")
                st.dataframe(
                    row_pct.style.format("{:.1f}").background_gradient(cmap="Blues", axis=1),
                    use_container_width=True,
                )
                st.caption(f"N = {grand_total:,} (non-missing pairs)")
