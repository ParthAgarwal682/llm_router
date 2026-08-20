"""Streamlit dashboard: cost view + verdict explorer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.storage import db

DB_PATH = ROOT / "data" / "router.db"

st.set_page_config(
    page_title="Router Arbitration Dashboard",
    page_icon=None,
    layout="wide",
)

st.title("Smart Router + Arbitration")
st.caption(f"Reading SQLite audit log at `{DB_PATH}`")

db.init_db(DB_PATH)
stats = db.get_stats(DB_PATH)
rows = db.list_requests(limit=200, db_path=DB_PATH)

tab_cost, tab_verdicts = st.tabs(["Cost view", "Verdict explorer"])

with tab_cost:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total requests", stats["total_requests"])
    c2.metric("Actual cost (USD)", f"{stats['total_cost_usd']:.6f}")
    c3.metric("Cost saved vs top model", f"{stats['cost_saved_usd']:.6f}")
    c4.metric("Escalation rate", f"{stats['escalation_rate']:.1%}")

    st.subheader("Model distribution")
    model_df = pd.DataFrame(stats["model_distribution"])
    if model_df.empty:
        st.info("No requests logged yet. Hit POST /v1/completions, then refresh.")
    else:
        st.bar_chart(model_df.set_index("model")["count"])
        st.dataframe(model_df, use_container_width=True)

    st.subheader("Tier distribution")
    tier_df = pd.DataFrame(stats["tier_distribution"])
    if not tier_df.empty:
        st.bar_chart(tier_df.set_index("tier")["count"])

    st.subheader("Baseline comparison")
    st.write(
        f"If every request had used **gpt4o** at the same token counts: "
        f"**${stats['total_baseline_cost_usd']:.6f}**. "
        f"Actual routed+verify cost: **${stats['total_cost_usd']:.6f}**."
    )

with tab_verdicts:
    st.subheader("Recent requests")
    if not rows:
        st.info("No rows yet.")
    else:
        overview = pd.DataFrame(
            [
                {
                    "id": r.id[:8],
                    "created_at": r.created_at,
                    "tier": r.tier,
                    "model": r.model_used,
                    "cost_usd": round(r.cost_usd, 6),
                    "verify": r.verify_verdict,
                    "promoted": r.promoted_to_arbitration,
                    "status": r.status,
                }
                for r in rows
            ]
        )
        st.dataframe(overview, use_container_width=True)

        options = {f"{r.id[:8]}… | {r.tier} | {r.verify_verdict or '-'} | {r.status}": r.id for r in rows}
        choice = st.selectbox("Inspect request", list(options.keys()))
        selected = db.get_request(options[choice], DB_PATH)
        if selected:
            st.markdown("#### Prompt")
            st.write(selected.prompt)
            st.markdown("#### Response")
            st.write(selected.response_text or "(empty)")
            st.markdown("#### Verification")
            st.write(
                {
                    "verdict": selected.verify_verdict,
                    "reason": selected.verify_reason,
                    "promoted_to_arbitration": selected.promoted_to_arbitration,
                    "status": selected.status,
                }
            )
            st.markdown("#### Arbitration verdict")
            if selected.verdict_json:
                try:
                    verdict = json.loads(selected.verdict_json)
                except json.JSONDecodeError:
                    verdict = selected.verdict_json
                st.json(verdict)
            else:
                st.write("No arbitration verdict (AGREE path or still running).")

st.button("Refresh")
