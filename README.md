# SPSS Data Explorer

A small Streamlit app for loading SPSS `.sav` files, browsing the data as a
spreadsheet, exporting CSV, and generating crosstabs.

## Features

- **Upload `.sav` files**; parsed with
  [pyreadstat](https://github.com/Roche/pyreadstat).
- **Browse data** in a sortable table (`st.dataframe`). Column headers show
  SPSS variable labels when available.
- **Download CSV** of the full dataset.
- **Crosstab analysis** between any two variables, with counts and row
  percentages. Value labels are applied automatically when present in the
  .sav metadata.

## Install and run

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Streamlit prints a local URL (default `http://localhost:8501`) — open it in
a browser.

## Deploy for free

For a free public URL, deploy to **Streamlit Community Cloud**
(<https://share.streamlit.io>):

1. Push this repo to GitHub.
2. Sign in at share.streamlit.io and connect the repo.
3. Set the main file to `streamlit_app.py` and deploy.

## Try it without your own data

A sample-file generator is included:

```bash
python generate_sample.py sample.sav
```

This writes `sample.sav` (500 rows, 8 variables with labels and value labels).
Upload it through the UI to explore.

## Usage

1. **Upload** a `.sav` file via the file picker.
2. **Browse** the full dataset. Click headers to sort.
3. **Download CSV** to get the full dataset as CSV.
4. **Crosstab.** Pick row and column variables, then **Generate crosstab**.
   You get a counts table (with row/column totals) and a row-percentage
   table with a heatmap.

## Notes

- Data is held in `st.session_state` per browser session.
- Encoding is auto-detected: UTF-8 first, LATIN1 fallback.

## File layout

```
/data/spss-app/
  streamlit_app.py    # Streamlit app
  generate_sample.py  # Make a test .sav file
  requirements.txt
  README.md
```
