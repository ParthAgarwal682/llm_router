"""Streamlit admin dashboard: Styled with Figma design tokens (Manrope, DM Sans, Sage Green, Terracotta)."""

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
    page_title="Router.ai — All Users & Total Savings",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Figma Theme CSS Injection (DM Sans, Manrope, Warm Cream, Sage, Terracotta)
# ---------------------------------------------------------------------------
FIGMA_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;450;500;550;600;700&family=Manrope:wght@500;600;650;700;800&display=swap');

/* Global Font & Background */
html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', -apple-system, sans-serif !important;
    background-color: #FAFAF7 !important;
    color: #2C302E !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Manrope', sans-serif !important;
    color: #343B33 !important;
    letter-spacing: -0.8px !important;
    font-weight: 700 !important;
}

/* Figma Brand Header */
.brand-header-wrap {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0 28px;
    border-bottom: 1px solid #ECECE6;
    margin-bottom: 28px;
}
.brand-left {
    display: flex;
    align-items: center;
    gap: 14px;
}
.brand-logo-badge {
    background: #D9744B;
    color: white;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    transform: rotate(-4deg);
    box-shadow: 0 4px 12px rgba(217, 116, 75, 0.25);
}
.brand-title-group h1 {
    font-size: 26px !important;
    margin: 0 !important;
    line-height: 1.15;
    letter-spacing: -1.2px !important;
}
.brand-title-group p {
    font-size: 11px;
    color: #92968B;
    margin: 3px 0 0;
}
.brand-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #F1F3E8;
    color: #46553B;
    border: 1px solid #E1E7D4;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
}
.pulse-dot {
    width: 7px;
    height: 7px;
    background: #73895D;
    border-radius: 50%;
}

/* Hero Cards Grid */
.stat-grid-figma {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 28px;
}
.figma-card {
    background: #FFFFFF;
    border: 1px solid #E7E9DE;
    border-radius: 12px;
    padding: 22px 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.015);
    position: relative;
    transition: transform 0.15s ease;
}
.figma-card:hover {
    transform: translateY(-2px);
}
.figma-card.sage-hero {
    background: #F4F6ED;
    border-color: #E1E7D4;
}
.card-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #8C947D;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.figma-card.sage-hero .card-label {
    color: #627052;
}
.card-val {
    font-family: 'Manrope', sans-serif;
    font-size: 32px;
    font-weight: 750;
    letter-spacing: -1.5px;
    color: #343B33;
    margin: 12px 0 6px;
    line-height: 1.1;
}
.figma-card.sage-hero .card-val {
    color: #46553B;
}
.card-sub {
    font-size: 11px;
    color: #989E8D;
    margin: 0;
}
.figma-card.sage-hero .card-sub {
    color: #707D63;
    font-weight: 500;
}
.saving-track {
    height: 4px;
    background: #E0E5D3;
    border-radius: 4px;
    margin-top: 14px;
    overflow: hidden;
}
.saving-fill {
    height: 100%;
    background: #9BA984;
    border-radius: 4px;
}

/* Tabs Styling */
div[data-baseweb="tab-list"] {
    background-color: #F2F4EB !important;
    padding: 4px !important;
    border-radius: 10px !important;
    gap: 4px !important;
    border: 1px solid #E6EAD9 !important;
    margin-bottom: 24px !important;
}
button[data-baseweb="tab"] {
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #7C856E !important;
    padding: 8px 16px !important;
    background: transparent !important;
    border: none !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: #FFFFFF !important;
    color: #46553B !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}

/* Streamlit Native Metric overrides */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E7E9DE;
    border-radius: 10px;
    padding: 16px 18px;
}
[data-testid="stMetricValue"] {
    font-family: 'Manrope', sans-serif !important;
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #46553B !important;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #8C947D !important;
    text-transform: uppercase;
}

/* Table styling */
[data-testid="stDataFrame"] {
    border: 1px solid #E7E9DE !important;
    border-radius: 10px !important;
    background: #FFFFFF !important;
    padding: 4px !important;
}

/* Action button */
.stButton>button {
    background: #D9744B !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    padding: 9px 18px !important;
    box-shadow: 0 2px 6px rgba(217, 116, 75, 0.2) !important;
    transition: background 0.15s ease !important;
}
.stButton>button:hover {
    background: #BB5B37 !important;
    color: #FFFFFF !important;
}

/* Pill badges */
.tier-pill-simple {
    background: #F1F3E8;
    color: #46553B;
    border: 1px solid #E1E7D4;
    padding: 3px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
}
.tier-pill-complex {
    background: #FAF1EB;
    color: #B56038;
    border: 1px solid #F2DACD;
    padding: 3px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
}
.saved-badge {
    background: #E8F4DC;
    color: #376321;
    border: 1px solid #D1E8BC;
    padding: 3px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 700;
}
</style>
"""

st.markdown(FIGMA_STYLE, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data Retrieval
# ---------------------------------------------------------------------------
db.init_db(DB_PATH)
stats = db.get_stats(DB_PATH)
users_data = db.list_users_with_savings(DB_PATH)
rows = db.list_requests(limit=300, db_path=DB_PATH)

total_baseline = stats.get("total_baseline_cost_usd", 0.0)
cost_saved = stats.get("cost_saved_usd", 0.0)
actual_cost = stats.get("total_cost_usd", 0.0)
saved_pct = (cost_saved / total_baseline * 100) if total_baseline > 0 else 0.0

# ---------------------------------------------------------------------------
# Header (Matching Figma Brand Symbol & Typography)
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="brand-header-wrap">
        <div class="brand-left">
            <div class="brand-logo-badge">⚡</div>
            <div class="brand-title-group">
                <h1>Router.ai <span style="color:#D9744B;">Console</span></h1>
                <p>Owner Dashboard · All Registered Users & Lifetime Arbitration Savings</p>
            </div>
        </div>
        <div>
            <span class="brand-badge">
                <span class="pulse-dot"></span>
                Connected: router.db
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Top 4 KPI Stat Cards (Figma Card Design with Sage Green Hero)
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="stat-grid-figma">
        <div class="figma-card sage-hero">
            <div class="card-label">
                <span>Total Net Savings</span>
                <span>💰</span>
            </div>
            <div class="card-val">${cost_saved:.4f}</div>
            <div class="card-sub">Saved vs 100% GPT-4o Baseline ({saved_pct:.1f}%)</div>
            <div class="saving-track">
                <div class="saving-fill" style="width: {min(max(saved_pct, 5.0), 100.0):.1f}%;"></div>
            </div>
        </div>
        <div class="figma-card">
            <div class="card-label">
                <span>Active Users</span>
                <span>👥</span>
            </div>
            <div class="card-val">{len(users_data)}</div>
            <div class="card-sub">Registered user accounts</div>
        </div>
        <div class="figma-card">
            <div class="card-label">
                <span>Total Prompts Routed</span>
                <span>⚡</span>
            </div>
            <div class="card-val">{stats.get('total_requests', 0):,}</div>
            <div class="card-sub">Via dynamic arbitration tiering</div>
        </div>
        <div class="figma-card">
            <div class="card-label">
                <span>Escalation Rate</span>
                <span>⚖️</span>
            </div>
            <div class="card-val">{stats.get('escalation_rate', 0.0):.1%}</div>
            <div class="card-sub">Promoted to multi-critic panel</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_users, tab_cost, tab_verdicts = st.tabs([
    "👥 All Users & Savings Breakdown",
    "📊 Cost Savings & Model Mix",
    "⚖️ Quality & Arbitration Inspector",
])

# ---------------------------------------------------------------------------
# Tab 1: All Users & Individual Savings
# ---------------------------------------------------------------------------
with tab_users:
    st.markdown("### Registered Users & Individual Financial Savings")
    st.caption("Inspect how much each user has spent vs baseline GPT-4o, and the dollar amount saved.")

    if not users_data:
        st.info("No registered users found yet. Users will appear here when they register at http://localhost:3000.")
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

        # Bar chart comparison
        active_users = user_df[user_df["total_requests"] > 0]
        if not active_users.empty:
            st.markdown("#### Cumulative Savings by User")
            st.bar_chart(
                active_users.set_index("email")["net_saved_usd"],
                color="#9BA984",
            )

    st.markdown("---")
    st.markdown("### Inspect Individual User Activity & Prompts")

    user_options = {u["email"]: u["id"] for u in users_data}
    if user_options:
        selected_email = st.selectbox("Select user account to inspect:", list(user_options.keys()))
        selected_user_id = user_options[selected_email]
        user_requests = [r for r in rows if getattr(r, "user_id", None) == selected_user_id]
        
        if user_requests:
            st.write(f"Showing **{len(user_requests)}** requests for `{selected_email}`:")
            u_overview = pd.DataFrame([
                {
                    "Request ID": r.id[:8],
                    "Timestamp": r.created_at,
                    "Prompt Preview": (r.prompt[:60] + "…") if len(r.prompt) > 60 else r.prompt,
                    "Tier": r.tier,
                    "Model Chosen": r.model_used,
                    "Actual Cost": f"${r.cost_usd:.5f}",
                    "Net Saved": f"${r.net_saved:.5f}" if r.net_saved is not None else "N/A",
                    "Status": r.status,
                }
                for r in user_requests
            ])
            st.dataframe(u_overview, use_container_width=True)
        else:
            st.info(f"User `{selected_email}` has not sent any prompt queries yet.")

# ---------------------------------------------------------------------------
# Tab 2: System Cost & Model Mix
# ---------------------------------------------------------------------------
with tab_cost:
    st.markdown("### Baseline vs Router Financial Audit")
    
    col_c1, col_c2, col_c3 = st.columns(3)
    col_c1.metric("GPT-4o Baseline Cost", f"${total_baseline:.4f}")
    col_c2.metric("Actual Router Spend", f"${actual_cost:.4f}")
    col_c3.metric("Net Dollars Kept", f"${cost_saved:.4f}", delta=f"{saved_pct:.1f}% saved")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Model Distribution")
        model_df = pd.DataFrame(stats.get("model_distribution", []))
        if not model_df.empty:
            st.bar_chart(model_df.set_index("model")["count"], color="#D9744B")
            st.dataframe(model_df, use_container_width=True)
        else:
            st.info("No model distribution data logged yet.")

    with col_b:
        st.markdown("#### Routing Tier Breakdown")
        tier_df = pd.DataFrame(stats.get("tier_distribution", []))
        if not tier_df.empty:
            st.bar_chart(tier_df.set_index("tier")["count"], color="#9BA984")
            st.dataframe(tier_df, use_container_width=True)
        else:
            st.info("No tier distribution data logged yet.")

# ---------------------------------------------------------------------------
# Tab 3: Verdict Explorer
# ---------------------------------------------------------------------------
with tab_verdicts:
    st.markdown("### Multi-Critic Arbitration & Audit Log")
    if not rows:
        st.info("No requests recorded yet.")
    else:
        overview = pd.DataFrame([
            {
                "Request ID": r.id[:8],
                "Timestamp": r.created_at,
                "Tier": r.tier,
                "Model": r.model_used,
                "Cost ($)": round(r.cost_usd, 6),
                "Verify Verdict": r.verify_verdict or "—",
                "Arbitrated": "Yes" if r.promoted_to_arbitration else "No",
                "Status": r.status,
            }
            for r in rows
        ])
        st.dataframe(overview, use_container_width=True)

        options = {f"{r.id[:8]}… | {r.tier} | {r.verify_verdict or '-'} | {r.status}": r.id for r in rows}
        choice = st.selectbox("Inspect deep trace for request:", list(options.keys()))
        selected = db.get_request(options[choice], db_path=DB_PATH)
        if selected:
            st.markdown("#### Prompt")
            st.write(selected.prompt)
            st.markdown("#### Response")
            st.write(selected.response_text or "(empty)")
            st.markdown("#### Verification Details")
            st.json({
                "verdict": selected.verify_verdict,
                "reason": selected.verify_reason,
                "promoted_to_arbitration": selected.promoted_to_arbitration,
                "status": selected.status,
            })
            if selected.verdict_json:
                st.markdown("#### Multi-Critic LangGraph Verdict")
                try:
                    verdict = json.loads(selected.verdict_json)
                except json.JSONDecodeError:
                    verdict = selected.verdict_json
                st.json(verdict)

st.markdown("---")
c_ref, _ = st.columns([1, 5])
with c_ref:
    if st.button("🔄 Refresh Data"):
        st.rerun()

