"""
app.py — Legal Resilience Engine: interactive demo UI

A thin Streamlit front-end over the same four pipeline modules used by
run_pipeline.py (ingest, store, analyse, notify). This is the surface you
actually drive during live judging: upload/paste a document, click Run, and
watch the pipeline identify affected clauses, explain why, and show the
redline fix — all in a browser instead of a terminal.

Why a second entry point instead of just the CLI:
- Judges can't watch a terminal scroll by during a 4-minute pitch as easily
  as they can follow a browser dashboard with a "Run" button they can even
  click themselves during Q&A.
- It reuses 100% of the pipeline logic (same functions, same JSON contracts)
  — this file adds *zero* new business logic, only presentation. That keeps
  "does the team understand their own code" easy to answer honestly.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import ingest
import store
import analyse
import notify

st.set_page_config(page_title="Legal Resilience Engine", page_icon="⚖️", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def render_diff_html(redline: str) -> str:
    """Convert analyse.py's [-deleted-]/{+added+} markers into inline HTML."""
    html = redline
    html = re.sub(r"\[-(.*?)-\]", r'<span style="background:#3a1414;color:#ff8080;text-decoration:line-through;padding:0 2px;border-radius:3px;">\1</span>', html)
    html = re.sub(r"\{\+(.*?)\+\}", r'<span style="background:#123a1c;color:#7CFC9C;padding:0 2px;border-radius:3px;">\1</span>', html)
    return html


def score_badge(score: int) -> str:
    if score > 7:
        color = "#ff4d4d"
    elif score > 4:
        color = "#e6c200"
    else:
        color = "#4dbb63"
    return f'<span style="background:{color};color:#111;padding:2px 10px;border-radius:12px;font-weight:600;">{score}</span>'


# ---------------------------------------------------------------------------
# Sidebar — inputs
# ---------------------------------------------------------------------------

st.sidebar.title("⚖️ Legal Resilience Engine")
st.sidebar.caption("Detect regulatory change impact on internal legal assets — before it causes harm.")

st.sidebar.subheader("1. Regulatory update")
reg_text = st.sidebar.text_area(
    "Paste the new/amended regulation text",
    value=ingest.SAMPLE_REGULATION,
    height=200,
)
reg_uploaded = st.sidebar.file_uploader("...or upload a regulation file (.pdf/.txt)", type=["pdf", "txt"], key="reg_upload")

st.sidebar.subheader("2. Internal legal asset")
asset_text = st.sidebar.text_area(
    "Paste the internal clause/template/playbook text",
    value=ingest.SAMPLE_INTERNAL_ASSET,
    height=200,
)
asset_uploaded = st.sidebar.file_uploader("...or upload an internal asset file (.pdf/.txt)", type=["pdf", "txt"], key="asset_upload")

run_clicked = st.sidebar.button("🚀 Run Resilience Analysis", type="primary", use_container_width=True)

with st.sidebar.expander("Settings"):
    st.write(
        "If `OPENROUTER_API_KEY` is set in the environment, analysis uses a "
        "live LLM (via `instructor` + Pydantic structured output). Otherwise "
        "it automatically falls back to a deterministic offline heuristic so "
        "the demo never breaks without internet/API access."
    )
    st.code(f"LLM available: {analyse._get_instructor_client() is not None}", language="text")


# ---------------------------------------------------------------------------
# Main — header
# ---------------------------------------------------------------------------

st.title("Legal Resilience Engine")
st.caption(
    "Structurally resilient compliance: identify which existing internal assets "
    "are affected by a regulatory change, understand *how*, and propagate the fix — "
    "before the outdated version causes harm."
)

if "report" not in st.session_state:
    st.session_state.report = None


def _extract_uploaded(file) -> str | None:
    if file is None:
        return None
    tmp_path = Path("sample_docs") / file.name
    tmp_path.parent.mkdir(exist_ok=True)
    tmp_path.write_bytes(file.getvalue())
    return ingest.extract_text(tmp_path)


if run_clicked:
    with st.status("Running pipeline...", expanded=True) as status:
        st.write("**Step 1/4 — Ingest:** chunking documents into citation-aware clauses...")
        reg_source = _extract_uploaded(reg_uploaded) or reg_text
        asset_source = _extract_uploaded(asset_uploaded) or asset_text

        chunks = []
        chunks.extend(ingest.chunk_legal_document(reg_source, "REGULATION", "Uploaded_Regulation"))
        chunks.extend(ingest.chunk_legal_document(asset_source, "INTERNAL_ASSET", "Uploaded_Internal_Asset"))
        ingest.OUTPUT_PATH.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
        st.write(f"Produced {len(chunks)} clause chunk(s).")

        st.write("**Step 2/4 — Store & Match:** embedding clauses and running semantic search...")
        pairs = store.run_matching()
        st.write(f"Found {len(pairs)} candidate regulation ↔ internal-asset pair(s) above similarity threshold.")

        st.write("**Step 3/4 — Analyse:** running structured legal impact analysis...")
        report = analyse.run_analysis()
        st.write(f"Analysed {len(report)} pair(s).")

        st.write("**Step 4/4 — Notify:** rendering dashboard and simulating propagation...")
        dispatch_result = notify.dispatch_updates(report, dry_run=True)
        st.write(f"Dry-run dispatched {dispatch_result['dispatched']} update notification(s).")

        status.update(label="Pipeline complete", state="complete", expanded=False)

    st.session_state.report = report

report = st.session_state.report

if report is None:
    st.info("Paste or upload a regulation and an internal asset in the sidebar, then click **Run Resilience Analysis**.")
    st.stop()

if not report:
    st.warning("No semantically related internal assets were found for this regulation (similarity below threshold).")
    st.stop()


# ---------------------------------------------------------------------------
# Main — summary table
# ---------------------------------------------------------------------------

st.subheader("Impact Summary")

df = pd.DataFrame([
    {
        "Asset": entry["asset"]["title"],
        "Clause": entry["asset"]["clause_reference"],
        "Similarity": entry["similarity_score"],
        "Impact Score": entry["analysis"]["impact_score"],
        "Status": "🔴 AFFECTED" if entry["analysis"]["is_affected"] else "🟢 Not affected",
        "Source": entry["analysis_source"],
    }
    for entry in report
])
st.dataframe(df, use_container_width=True, hide_index=True)

affected_entries = [e for e in report if e["analysis"]["is_affected"]]
col1, col2, col3 = st.columns(3)
col1.metric("Clauses scanned", len(report))
col2.metric("Flagged as affected", len(affected_entries))
col3.metric(
    "Highest impact score",
    max((e["analysis"]["impact_score"] for e in report), default=0),
)


# ---------------------------------------------------------------------------
# Main — per-clause detail: redline diff + reasoning
# ---------------------------------------------------------------------------

st.subheader("Affected Clauses — Redline & Reasoning")

if not affected_entries:
    st.success("No affected clauses detected — internal assets appear compliant with this regulatory change.")

for entry in affected_entries:
    with st.expander(
        f"{entry['asset']['title']} ({entry['asset']['clause_reference']}) — impact {entry['analysis']['impact_score']}/10",
        expanded=True,
    ):
        st.markdown(f"**Impact score:** {score_badge(entry['analysis']['impact_score'])}", unsafe_allow_html=True)
        st.markdown("**Redline diff** (red = removed, green = added):")
        st.markdown(
            f'<div style="font-family:monospace;line-height:1.6;padding:10px;background:#111;border-radius:6px;">{render_diff_html(entry["redline_diff"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**Legal reasoning:** {entry['analysis']['legal_reasoning']}")
        st.markdown(f"**Statutory citations:** {', '.join(entry['analysis']['statutory_citations']) or 'N/A'}")
        st.caption(f"Analysis source: {entry['analysis_source']} · Similarity: {entry['similarity_score']}")

st.divider()
if Path("updated_playbook.md").exists():
    with st.expander("📄 Auto-propagated playbook (updated_playbook.md)"):
        st.markdown(Path("updated_playbook.md").read_text(encoding="utf-8"))
