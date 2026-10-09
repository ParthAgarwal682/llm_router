"""Streamlit admin dashboard: users breakdown + individual savings + cost view + verdict explorer."""

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
    page_title="LLM Router Admin & Savings Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ LLM Router — Executive Admin Dashboard")
st.caption(f"System audit log connected to `{DB_PATH}`")

db.init_db(DB_PATH)
stats = db.get_stats(DB_PATH)
users_data = db.list_users_with_savings(DB_PATH)
rows = db.list_requests(limit=300, db_path=DB_PATH)

# Top KPI Metric Cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Money Saved (USD)", f"${stats['cost_saved_usd']:.4f}")
c2.metric("Total Registered Users", len(users_data))
c3.metric("Total Requests Processed", stats["total_requests"])
c4.metric("Escalation Rate", f"{stats['escalation_rate']:.1%}")

tab_users, tab_cost, tab_verdicts = st.tabs([
    "👥 Current Users & Savings",
    "📊 System Cost & Model Mix",
    "⚖️ Quality & Arbitration Explorer",
])

# ---------------------------------------------------------------------------
# Tab 1: Current Users & Individual Savings
# ---------------------------------------------------------------------------
with tab_users:
    st.subheader("Registered Users & Individual Savings Breakdown")
    if not users_data:
        st.info("No registered users found yet. Users will appear here when they sign up at http://localhost:3000.")
    else:
        user_df = pd.DataFrame(users_data)
        display_df = user_df[[
            "email", "total_requests", "net_saved_usd", "saved_percent", 
            "actual_cost_usd", "baseline_cost_usd", "created_at"
        ]].copy()
        
        display_df.columns = [
            "User Email", "Requests", "Net Dollar Saved ($)", "Savings %",
            "Actual Cost ($)", "GPT-4o Baseline ($)", "Joined Date"
        ]
        
        display_df["Net Dollar Saved ($)"] = display_df["Net Dollar Saved ($)"].apply(lambda x: f"${x:.4f}")
        display_df["Actual Cost ($)"] = display_df["Actual Cost ($)"].apply(lambda x: f"${x:.4f}")
        display_df["GPT-4o Baseline ($)"] = display_df["GPT-4o Baseline ($)"].apply(lambda x: f"${x:.4f}")
        display_df["Savings %"] = display_df["Savings %"].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(display_df, use_container_width=True)

        st.subheader("Savings Comparison Across Users")
        chart_data = user_df[user_df["total_requests"] > 0]
        if not chart_data.empty:
            st.bar_chart(chart_data.set_index("email")["net_saved_usd"])
        else:
            st.caption("No prompt activity recorded yet for current registered users.")

    st.divider()
    st.subheader("Inspect User Activity")
    user_options = {u["email"]: u["id"] for u in users_data}
    if user_options:
        selected_email = st.selectbox("Select user to inspect prompt history", list(user_options.keys()))
        selected_user_id = user_options[selected_email]
        user_requests = [r for r in rows if getattr(r, "user_id", None) == selected_user_id]
        if user_requests:
            st.write(f"Showing **{len(user_requests)}** requests for `{selected_email}`:")
            u_overview = pd.DataFrame([
                {
                    "id": r.id[:8],
                    "time": r.created_at,
                    "prompt": (r.prompt[:60] + "...") if len(r.prompt) > 60 else r.prompt,
                    "tier": r.tier,
                    "model": r.model_used,
                    "actual_cost": f"${r.cost_usd:.5f}",
                    "net_saved": f"${r.net_saved:.5f}" if r.net_saved is not None else "N/A",
                    "status": r.status,
                }
                for r in user_requests
            ])
            st.dataframe(u_overview, use_container_width=True)
        else:
            st.info(f"User `{selected_email}` has not sent any chat queries yet.")

# ---------------------------------------------------------------------------
# Tab 2: System Cost & Model Mix
# ---------------------------------------------------------------------------
with tab_cost:
    st.subheader("Baseline Cost Comparison")
    saved_pct = (stats['cost_saved_usd'] / stats['total_baseline_cost_usd'] * 100) if stats['total_baseline_cost_usd'] > 0 else 0.0
    st.write(
        f"If all requests were sent to **GPT-4o**: "
        f"**${stats['total_baseline_cost_usd']:.4f}**.<br>"
        f"Actual routed + background verification cost: "
        f"**${stats['total_cost_usd']:.4f}**.<br>"
        f"**Net Profit/Savings Generated:** "
        f"**${stats['cost_saved_usd']:.4f}** ({saved_pct:.1f}% savings).",
        unsafe_allow_html=True,
    )
    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Model Distribution")
        model_df = pd.DataFrame(stats["model_distribution"])
        if not model_df.empty:
            st.bar_chart(model_df.set_index("model")["count"])
            st.dataframe(model_df, use_container_width=True)
        else:
            st.info("No model distribution data logged yet.")

    with col_b:
        st.subheader("Tier Distribution")
        tier_df = pd.DataFrame(stats["tier_distribution"])
        if not tier_df.empty:
            st.bar_chart(tier_df.set_index("tier")["count"])
            st.dataframe(tier_df, use_container_width=True)
        else:
            st.info("No tier distribution data logged yet.")

# ---------------------------------------------------------------------------
# Tab 3: Verdict Explorer
# ---------------------------------------------------------------------------
with tab_verdicts:
    st.subheader("Recent Requests & Arbitration Verdicts")
    if not rows:
        st.info("No requests recorded yet.")
    else:
        overview = pd.DataFrame([
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
        ])
        st.dataframe(overview, use_container_width=True)

        options = {f"{r.id[:8]}… | {r.tier} | {r.verify_verdict or '-'} | {r.status}": r.id for r in rows}
        choice = st.selectbox("Inspect specific request audit", list(options.keys()))
        selected = db.get_request(options[choice], DB_PATH)
        if selected:
            st.markdown("#### Prompt")
            st.write(selected.prompt)
            st.markdown("#### Response")
            st.write(selected.response_text or "(empty)")
            st.markdown("#### Verification Details")
            st.write({
                "verdict": selected.verify_verdict,
                "reason": selected.verify_reason,
                "promoted_to_arbitration": selected.promoted_to_arbitration,
                "status": selected.status,
            })
            st.markdown("#### Multi-Critic LangGraph Verdict")
            if selected.verdict_json:
                try:
                    verdict = json.loads(selected.verdict_json)
                except json.JSONDecodeError:
                    verdict = selected.verdict_json
                st.json(verdict)
            else:
                st.write("No arbitration escalation required (Single-Judge AGREE path or pending).")

st.button("🔄 Refresh Data")
