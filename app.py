import gradio as gr
import pyreadstat
import pandas as pd
import re
from collections import defaultdict

# ── State ─────────────────────────────────────────────────────────────────────
_df   = {}
_meta = {}
_tree = {}

# ── Section detection ─────────────────────────────────────────────────────────
NAMED_SECTIONS = {'DEM','QUAL','CONTROL','FILTER','HM','FAC','SM','HH','COUNTRY'}

def detect_section(name):
    # Priority 1: single letter + digit -> Section A, B, C...
    m1 = re.match(r'^([A-Z])(\d)', name)
    if m1:
        return 'Section ' + m1.group(1)
    # Priority 2: lowercase system vars
    if name and name[0].islower():
        return 'System'
    # Priority 3: named prefix
    m2 = re.match(r'^([A-Z]{2,})', name)
    if m2:
        prefix = m2.group(1)
        for length in range(len(prefix), 1, -1):
            if prefix[:length] in NAMED_SECTIONS:
                return prefix[:length]
        return prefix
    return 'Other'

# ── Tree builder ──────────────────────────────────────────────────────────────

def parse_variable_tree(meta):
    tree = defaultdict(lambda: defaultdict(lambda: {'label': '', 'variables': []}))

    for name in meta.column_names:
        raw_label = meta.column_names_to_labels.get(name) or name
        section   = detect_section(name)

        # Extract question code + item from label format:
        # "E7x1. ArkenZoo[question text]"  or  "DEM1. Kön:"
        m_q = re.match(r'^(\S+?)[.]\s+(.+?)(?:\[(.+)\])?\s*$', raw_label)
        if m_q and re.match(r'^[A-Z][A-Z0-9_x]*$', m_q.group(1)):
            q_code    = m_q.group(1)
            item_name = m_q.group(2).strip()
            q_text    = m_q.group(3) if m_q.group(3) else m_q.group(2)
        else:
            # Fallback: extract question code from variable name
            # A1a_SE_1 -> A1a,  E7x1_3 -> E7x1,  DEM3A_SE -> DEM3A
            m_qcode = re.match(r'^([A-Za-z]+\d+[a-z]?(?:x\d+)?)', name)
            q_code    = m_qcode.group(1) if m_qcode else name
            item_name = ''
            q_text    = raw_label

        if not tree[section][q_code]['label'] and q_text:
            tree[section][q_code]['label'] = q_text
        elif not tree[section][q_code]['label']:
            tree[section][q_code]['label'] = q_code

        tree[section][q_code]['variables'].append({
            'name':      name,
            'raw_label': raw_label,
            'item':      item_name or name,
        })

    return tree

def render_tree_html(tree):
    html = '<div style="font-family:monospace;font-size:13px;line-height:1.7">'
    for section in sorted(tree.keys()):
        q_map = tree[section]
        total = sum(len(v['variables']) for v in q_map.values())
        html += (
            '<details>'
            f'<summary style="cursor:pointer;font-weight:bold;color:#1a73e8;padding:4px 0">'
            f'\U0001f4c2 {section} '
            f'<span style="color:#999;font-weight:normal;font-size:11px">{total} vars</span>'
            '</summary>'
            '<div style="padding-left:18px;border-left:2px solid #e8eaed;margin-left:6px">'
        )
        for q_code in sorted(q_map.keys()):
            q       = q_map[q_code]
            q_label = q['label'][:90] + ('\u2026' if len(q['label']) > 90 else '')
            n_vars  = len(q['variables'])
            html += (
                '<details>'
                f'<summary style="cursor:pointer;color:#333;padding:2px 0">'
                f'\U0001f4cb <b>{q_code}</b> \u2014 '
                f'<span style="color:#555">{q_label}</span> '
                f'<span style="color:#aaa;font-size:11px">({n_vars})</span>'
                '</summary>'
                '<div style="padding-left:16px;border-left:2px solid #f0f0f0;margin-left:6px">'
            )
            for v in q['variables']:
                html += (
                    f'<div style="padding:1px 4px">'
                    f'<code style="color:#c0392b">{v["name"]}</code>'
                    f'<span style="color:#666"> \u2014 {v["item"]}</span>'
                    '</div>'
                )
            html += '</div></details>'
        html += '</div></details>'
    html += '</div>'
    return html

# ── Gradio callbacks ──────────────────────────────────────────────────────────

def load_file(file):
    global _df, _meta, _tree
    if file is None:
        return "No file uploaded.", "", [], []
    try:
        df, meta = pyreadstat.read_sav(file.name)
        _df   = df
        _meta = meta
        _tree = parse_variable_tree(meta)

        n_vars     = len(meta.column_names)
        n_rows     = len(df)
        n_sections = len(_tree)
        summary = (
            f"\u2705 **{file.name.split('/')[-1]}** \u2014 "
            f"{n_vars:,} variables \u00b7 {n_rows:,} rows \u00b7 {n_sections} sections"
        )
        tree_html   = render_tree_html(_tree)
        var_choices = [
            (f"{n}  {(meta.column_names_to_labels.get(n) or '')[:55]}", n)
            for n in meta.column_names
        ]
        return summary, tree_html, var_choices, var_choices
    except Exception as e:
        return f"\u274c Error: {e}", "", [], []

def browse_data():
    if not _df:
        return "No data loaded."
    return pd.DataFrame(_df).head(100).to_html(border=0, classes="table")

def export_csv():
    if not _df:
        return None
    path = "/tmp/export.csv"
    pd.DataFrame(_df).to_csv(path, index=False)
    return path

def run_crosstab(row_var, col_var):
    if not _df or not row_var or not col_var:
        return "Select row and column variables first."
    if row_var not in _df.columns or col_var not in _df.columns:
        return "Variable not found in loaded data."
    try:
        ct  = pd.crosstab(_df[row_var], _df[col_var], margins=True)
        pct = pd.crosstab(_df[row_var], _df[col_var], normalize='index').mul(100).round(1)
        pct.columns = [f"{c} %" for c in pct.columns]
        combined = pd.concat([ct, pct], axis=1)
        return combined.to_html(border=0, classes="table")
    except Exception as e:
        return f"Error: {e}"

# ── Layout ────────────────────────────────────────────────────────────────────
css = """
.table { border-collapse:collapse; width:100%; font-size:13px; }
.table th, .table td { border:1px solid #e0e0e0; padding:4px 8px; text-align:left; }
.table tr:nth-child(even) { background:#f9f9f9; }
"""

with gr.Blocks(title="SPSS Data Explorer", theme=gr.themes.Soft(), css=css) as demo:
    gr.Markdown("# \U0001f4ca SPSS Data Explorer")

    file_input = gr.File(label="Upload .sav file", file_types=[".sav"])
    status_md  = gr.Markdown("")

    with gr.Tabs():

        with gr.Tab("\U0001f333 Variable Tree"):
            gr.Markdown(
                "_Expand sections \u2192 questions \u2192 variables. "
                "Variable names in red can be copied into the Crosstab tab._"
            )
            tree_html_out = gr.HTML()

        with gr.Tab("\U0001f4cb Browse Data"):
            browse_btn  = gr.Button("Show first 100 rows", variant="primary")
            data_html   = gr.HTML()
            export_btn  = gr.Button("Export to CSV")
            export_file = gr.File(label="Download CSV")

        with gr.Tab("\U0001f4ca Crosstab"):
            with gr.Row():
                row_dd = gr.Dropdown(label="Row variable",    choices=[], interactive=True)
                col_dd = gr.Dropdown(label="Column variable", choices=[], interactive=True)
            run_btn      = gr.Button("Run crosstab", variant="primary")
            crosstab_out = gr.HTML()

    # Wire
    file_input.change(
        load_file,
        inputs=[file_input],
        outputs=[status_md, tree_html_out, row_dd, col_dd]
    )
    browse_btn.click(browse_data,   inputs=[],              outputs=[data_html])
    export_btn.click(export_csv,    inputs=[],              outputs=[export_file])
    run_btn.click(   run_crosstab,  inputs=[row_dd, col_dd], outputs=[crosstab_out])

demo.launch(server_name="0.0.0.0", server_port=7860)
