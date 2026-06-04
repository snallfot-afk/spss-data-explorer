"""SPSS Data Explorer — Streamlit app.

Loads .sav files via pyreadstat, browses data, exports CSV, and
generates crosstabs with counts and row percentages.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd
import pyreadstat
import streamlit as st


st.set_page_config(page_title="SPSS Data Explorer", layout="wide")


def read_sav(path: str):
    """Read a .sav file, trying utf-8 then latin-1."""
    try:
        return pyreadstat.read_sav(path, apply_value_formats=False)
    except UnicodeDecodeError:
        return pyreadstat.read_sav(path, apply_value_formats=False, encoding="LATIN1")


def value_labels_map(meta) -> dict[str, dict]:
    """Build {variable_name: {raw_value: label}} from pyreadstat meta."""
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
    """Return the series with value labels applied if available."""
    s = df[var]
    labels = value_labels.get(var)
    if labels:
        def _map(v):
            if pd.isna(v):
                return None
            if isinstance(v, (int, float, np.integer, np.floating)) and float(v).is_integer():
                key = str(int(v))
            else:
                key = str(v)
            return labels.get(key, labels.get(str(v), str(v)))
        return s.map(_map)
    return s.where(s.notna(), None).astype(object).map(
        lambda v: None if v is None else str(v)
    )


def load_uploaded_file(uploaded_file) -> None:
    """Parse the uploaded .sav file and store results in session_state."""
    # Read all bytes first before writing to temp file
    file_bytes = uploaded_file.read()
    with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        df, meta = read_sav(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    column_labels = {
        name: lbl
        for name, lbl in zip(meta.column_names, meta.column_labels or [])
        if lbl
    }
    st.session_state.df = df
    st.session_state.meta = meta
    st.session_state.column_labels = column_labels
    st.session_state.value_labels = value_labels_map(meta)
    st.session_state.filename = uploaded_file.name


# Sidebar
with st.sidebar:
    st.title("SPSS Data Explorer")
    st.markdown(
        """
        Upload an SPSS `.sav` file to:

        1. **Browse** the data as a sortable table
        2. **Download** as CSV
        3. **Crosstab** any two variables with counts and row %

        Value labels and variable labels are read from the .sav metadata
        automatically. Encoding falls back from UTF-8 to LATIN1.
        """
    )

# Main
uploaded = st.file_uploader("Upload a .sav file", type=["sav"])

if uploaded is not None:
    if st.session_state.get("filename") != uploaded.name:
        with st.spinner(f"Reading {uploaded.name}…"):
            try:
                load_uploaded_file(uploaded)
                st.success(f"✓ Loaded {uploaded.name}")
            except Exception as exc:  # noqa: BLE001
                import traceback
                st.error(f"Failed to read .sav file: {exc}")
                st.code(traceback.format_exc())
                st.stop()

df: pd.DataFrame | None = st.session_state.get("df")

if df is None:
    st.info("Upload a .sav file to get started. Try `python generate_sample.py` for a test file.")
    st.stop()

column_labels: dict[str, str] = st.session_state.get("column_labels", {})
value_labels: dict[str, dict] = st.session_state.get("value_labels", {})
filename: str = st.session_state.get("filename", "data.sav")

# Dataset info
rows, cols = df.shape
labeled_count = sum(1 for c in df.columns if c in column_labels)
c1, c2, c3, c4 = st.columns(4)
c1.metric("File", filename)
c2.metric("Rows", f"{rows:,}")
c3.metric("Columns", f"{cols:,}")
c4.metric("Labeled vars", f"{labeled_count}/{cols}")

# Data browser
st.subheader("Data")
header_map = {c: column_header(c, column_labels) for c in df.columns}
display_df = df.rename(columns=header_map)
st.dataframe(display_df, use_container_width=True, height=480)

# CSV download
csv_bytes = df.to_csv(index=False).encode("utf-8")
download_name = os.path.splitext(filename)[0] + ".csv"
st.download_button(
    "Download CSV",
    data=csv_bytes,
    file_name=download_name,
    mime="text/csv",
)

# Crosstab
st.subheader("Crosstab")

var_options = list(df.columns)
def _fmt(v: str) -> str:
    return column_header(v, column_labels)

col_a, col_b = st.columns(2)
row_var = col_a.selectbox("Row variable", var_options, format_func=_fmt, key="row_var")
col_var = col_b.selectbox(
    "Column variable",
    var_options,
    index=min(1, len(var_options) - 1),
    format_func=_fmt,
    key="col_var",
)

if st.button("Generate crosstab"):
    if row_var == col_var:
        st.warning("Pick two different variables.")
    else:
        r = labeled_series(df, row_var, value_labels)
        c = labeled_series(df, col_var, value_labels)
        work = pd.DataFrame({"r": r, "c": c}).dropna()
        if work.empty:
            st.warning("No non-missing data for this variable pair.")
        else:
            counts = pd.crosstab(work["r"], work["c"])
            counts = counts.sort_index().reindex(
                sorted(counts.columns, key=str), axis=1
            )
            row_totals = counts.sum(axis=1)
            col_totals = counts.sum(axis=0)
            grand_total = int(counts.values.sum())

            row_pct = counts.div(row_totals.replace(0, np.nan), axis=0) * 100.0
            row_pct = row_pct.fillna(0.0).round(1)

            counts_out = counts.copy()
            counts_out["Total"] = row_totals
            totals_row = pd.Series(
                {c: int(col_totals[c]) for c in counts.columns}, name="Total"
            )
            totals_row["Total"] = grand_total
            counts_out = pd.concat([counts_out, totals_row.to_frame().T])

            st.markdown(
                f"**Counts** — rows: *{column_header(row_var, column_labels)}*, "
                f"columns: *{column_header(col_var, column_labels)}*"
            )
            st.dataframe(counts_out, use_container_width=True)

            st.markdown("**Row percentages (%)**")
            st.dataframe(
                row_pct.style.format("{:.1f}").background_gradient(
                    cmap="Blues", axis=1
                ),
                use_container_width=True,
            )

            st.caption(f"N = {grand_total:,} (non-missing pairs)")
