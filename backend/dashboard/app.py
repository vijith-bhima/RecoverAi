"""
dashboard/app.py — RecoverAI Streamlit dashboard.

Run with: streamlit run dashboard/app.py

Three views:
  1. 📊 Overview   — live batch metrics, charts, KPI cards
  2. 📋 Audit Log  — paginated table of all pipeline decisions
  3. 🔍 Payment    — look up one payment's full audit trail
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd

from db import get_connection
from evaluate import load_all_payments, run_pipeline, compute_metrics
from core.audit import print_audit, get_audit_entry

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RecoverAI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Dark gradient background */
    .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

    /* KPI card */
    .kpi-card {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 20px 24px;
        text-align: center;
        backdrop-filter: blur(10px);
    }
    .kpi-label { color: #a0aec0; font-size: 0.78rem; text-transform: uppercase;
                 letter-spacing: 0.1em; margin-bottom: 6px; }
    .kpi-value { color: #ffffff; font-size: 2.1rem; font-weight: 700;
                 line-height: 1.1; }
    .kpi-sub   { color: #68d391; font-size: 0.82rem; margin-top: 4px; }

    /* Section header */
    .section-title {
        color: #e2e8f0;
        font-size: 1.15rem;
        font-weight: 600;
        margin: 28px 0 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    /* Metric pill */
    .pill {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .pill-green  { background: rgba(72,187,120,0.2); color: #68d391; }
    .pill-red    { background: rgba(245,101,101,0.2); color: #fc8181; }
    .pill-yellow { background: rgba(236,201,75,0.2);  color: #f6e05e; }
    .pill-blue   { background: rgba(99,179,237,0.2);  color: #90cdf4; }

    /* Hide Streamlit default header */
    header[data-testid="stHeader"] { background: transparent; }

    /* Table styling */
    .stDataFrame { border-radius: 12px; overflow: hidden; }

    /* Audit box */
    .audit-box {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 20px;
        font-family: 'Courier New', monospace;
        font-size: 0.87rem;
        color: #e2e8f0;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)


# ── Data helpers ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_metrics_cached():
    """Run batch evaluation and cache for 60 seconds."""
    records = load_all_payments()
    results = [run_pipeline(p, c) for p, c in records]
    m = compute_metrics(results)
    return m, results


@st.cache_data(ttl=30, show_spinner=False)
def get_audit_table():
    """Load audit_logs joined with payment details."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.event_id,
                a.payment_id,
                p.amount,
                p.failure_reason,
                a.ml_score,
                a.ai_diagnosis,
                a.ai_recommendation,
                a.guardrail_result,
                a.action_taken,
                a.result,
                a.timestamp
            FROM audit_logs a
            JOIN payments p ON a.payment_id = p.payment_id
            ORDER BY a.timestamp DESC
            LIMIT 500
            """,
        ).fetchall()
    return [dict(r) for r in rows]


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 20px 0 10px;'>
        <span style='font-size:2.4rem;'>⚡</span>
        <h2 style='color:#e2e8f0; margin:8px 0 0; font-size:1.4rem;'>RecoverAI</h2>
        <p style='color:#718096; font-size:0.8rem; margin:4px 0 0;'>
            Razorpay AI Buildathon<br>Track 03 — Revenue Recovery
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📊 Overview", "📋 Audit Log", "🔍 Payment Lookup"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("""
    <div style='color:#718096; font-size:0.75rem; padding: 8px 0;'>
        <b style='color:#a0aec0;'>Architecture</b><br><br>
        ML predicts →<br>
        LLM reasons →<br>
        Rules protect →<br>
        Code executes →<br>
        Metrics measure
    </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE 1: Overview
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if page == "📊 Overview":
    st.markdown(
        "<h1 style='color:#e2e8f0; font-size:1.8rem; margin-bottom:4px;'>"
        "⚡ RecoverAI — Live Dashboard</h1>"
        "<p style='color:#718096; margin-bottom:24px;'>"
        "Real-time metrics from the payment recovery pipeline</p>",
        unsafe_allow_html=True,
    )

    with st.spinner("Running batch evaluation…"):
        m, results = get_metrics_cached()

    # ── KPI cards row 1 ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>Revenue at Risk</div>
            <div class='kpi-value'>₹{m['total_amount']/1e5:.1f}L</div>
            <div class='kpi-sub'>across {m['n']} payments</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>Revenue Recovered</div>
            <div class='kpi-value'>₹{m['revenue_recovered']/1e5:.1f}L</div>
            <div class='kpi-sub'>{m['revenue_recovered']/m['total_amount']:.1%} of at-risk</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>Recovery Rate</div>
            <div class='kpi-value'>{m['recovery_rate']:.1f}%</div>
            <div class='kpi-sub'>{m['successful']} of {m['recoverable_count']} recoverable</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>ML F1 Score</div>
            <div class='kpi-value'>{m['f1']:.3f}</div>
            <div class='kpi-sub'>P={m['precision']:.3f} · R={m['recall']:.3f}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI cards row 2 ───────────────────────────────────────────────────────
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>Total Processed</div>
            <div class='kpi-value'>{m['n']}</div>
            <div class='kpi-sub'>failed payments</div>
        </div>""", unsafe_allow_html=True)
    with c6:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>Human Escalations</div>
            <div class='kpi-value'>{m['human_escalations']}</div>
            <div class='kpi-sub'>{m['human_escalations']/m['n']:.1%} of total</div>
        </div>""", unsafe_allow_html=True)
    with c7:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>Guardrail Blocks</div>
            <div class='kpi-value'>{m['guardrail_blocks']}</div>
            <div class='kpi-sub'>safety interventions</div>
        </div>""", unsafe_allow_html=True)
    with c8:
        st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>True Positives</div>
            <div class='kpi-value'>{m['tp']}</div>
            <div class='kpi-sub'>correct recovery predictions</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("<div class='section-title'>Recovery Rate by Failure Reason</div>",
                    unsafe_allow_html=True)

        df_results = pd.DataFrame(results)
        by_reason  = df_results.groupby("failure_reason").agg(
            total    = ("recovered", "count"),
            recovered= ("recovered", "sum"),
        ).reset_index()
        by_reason["rate"] = by_reason["recovered"] / by_reason["total"] * 100

        # Sort for visual clarity
        by_reason = by_reason.sort_values("rate", ascending=True)

        chart_data = pd.DataFrame({
            "Failure Reason": by_reason["failure_reason"],
            "Recovery Rate %": by_reason["rate"].round(1),
        }).set_index("Failure Reason")

        st.bar_chart(chart_data, color="#6366f1", height=280)

    with col_right:
        st.markdown("<div class='section-title'>Prediction Confusion Matrix</div>",
                    unsafe_allow_html=True)

        confusion_df = pd.DataFrame({
            "": ["Predicted +", "Predicted −"],
            "Actual +": [m["tp"], m["fn"]],
            "Actual −": [m["fp"], m["tn"]],
        }).set_index("")

        st.dataframe(
            confusion_df.style.background_gradient(cmap="Blues"),
            use_container_width=True,
        )

        st.markdown(f"""
        <br>
        <div style='display:flex; gap:8px; flex-wrap:wrap;'>
            <span class='pill pill-green'>Precision {m['precision']:.3f}</span>
            <span class='pill pill-blue'>Recall {m['recall']:.3f}</span>
            <span class='pill pill-yellow'>F1 {m['f1']:.3f}</span>
        </div>""", unsafe_allow_html=True)

    # ── Revenue chart ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>Revenue Distribution by Outcome</div>",
                unsafe_allow_html=True)

    revenue_df = pd.DataFrame({
        "Category": ["Recovered", "Not Recovered", "Escalated/Pending"],
        "Amount (₹)": [
            m["revenue_recovered"],
            m["total_amount"] - m["revenue_recovered"] - sum(
                r["amount"] for r in results if r["outcome"] == "PENDING"
            ),
            sum(r["amount"] for r in results if r["outcome"] == "PENDING"),
        ]
    }).set_index("Category")

    st.bar_chart(revenue_df, height=200)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE 2: Audit Log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "📋 Audit Log":
    st.markdown(
        "<h1 style='color:#e2e8f0; font-size:1.8rem; margin-bottom:4px;'>"
        "📋 Audit Log</h1>"
        "<p style='color:#718096; margin-bottom:24px;'>"
        "Every pipeline decision — ML → AI → Guardrail → Outcome</p>",
        unsafe_allow_html=True,
    )

    rows = get_audit_table()

    if not rows:
        st.info("No audit records yet. Run `python evaluate.py` first.")
        st.stop()

    df = pd.DataFrame(rows)

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        reason_filter = st.multiselect(
            "Failure Reason",
            options=sorted(df["failure_reason"].unique()),
            default=[],
        )
    with fc2:
        result_filter = st.multiselect(
            "Outcome",
            options=sorted(df["result"].unique()),
            default=[],
        )
    with fc3:
        guardrail_filter = st.multiselect(
            "Guardrail",
            options=sorted(df["guardrail_result"].unique()),
            default=[],
        )

    filtered = df.copy()
    if reason_filter:
        filtered = filtered[filtered["failure_reason"].isin(reason_filter)]
    if result_filter:
        filtered = filtered[filtered["result"].isin(result_filter)]
    if guardrail_filter:
        filtered = filtered[filtered["guardrail_result"].isin(guardrail_filter)]

    st.markdown(f"**{len(filtered)}** records" + (" (filtered)" if any([reason_filter, result_filter, guardrail_filter]) else ""))

    # Display table with colour-coded outcome column
    display_df = filtered[[
        "payment_id", "failure_reason", "amount", "ml_score",
        "ai_recommendation", "guardrail_result", "action_taken", "result", "timestamp"
    ]].rename(columns={
        "payment_id":      "Payment",
        "failure_reason":  "Failure",
        "amount":          "Amount (₹)",
        "ml_score":        "ML Score",
        "ai_recommendation": "AI Rec.",
        "guardrail_result":"Guardrail",
        "action_taken":    "Action",
        "result":          "Outcome",
        "timestamp":       "Timestamp",
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        height=480,
        column_config={
            "Amount (₹)": st.column_config.NumberColumn(format="₹%.2f"),
            "ML Score":   st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
        },
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE 3: Payment Lookup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "🔍 Payment Lookup":
    st.markdown(
        "<h1 style='color:#e2e8f0; font-size:1.8rem; margin-bottom:4px;'>"
        "🔍 Payment Lookup</h1>"
        "<p style='color:#718096; margin-bottom:24px;'>"
        "Enter a payment ID to see the complete audit trail</p>",
        unsafe_allow_html=True,
    )

    # Get a list of payment IDs that have audit records for the dropdown
    with get_connection() as conn:
        audit_ids = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT payment_id FROM audit_logs ORDER BY timestamp DESC LIMIT 100"
            ).fetchall()
        ]

    col_input, col_btn = st.columns([3, 1])
    with col_input:
        pid = st.selectbox(
            "Payment ID",
            options=audit_ids,
            index=0 if audit_ids else None,
            placeholder="Select a payment…",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        lookup = st.button("🔍 Look up", use_container_width=True, type="primary")

    if lookup and pid:
        entry = get_audit_entry(pid)

        if entry is None:
            st.error(f"No audit record found for `{pid}`. Run the pipeline on this payment first.")
        else:
            # Payment details
            with get_connection() as conn:
                p_row = conn.execute(
                    "SELECT * FROM payments WHERE payment_id = ?", (pid,)
                ).fetchone()

            st.markdown("<br>", unsafe_allow_html=True)

            # Two column layout
            left, right = st.columns(2)

            with left:
                st.markdown("<div class='section-title'>Payment Details</div>",
                            unsafe_allow_html=True)
                if p_row:
                    d = dict(p_row)
                    st.markdown(f"""
                    | Field | Value |
                    |---|---|
                    | Payment ID | `{d['payment_id']}` |
                    | Customer | `{d['customer_id']}` |
                    | Amount | ₹{d['amount']:,.2f} |
                    | Failure | `{d['failure_reason']}` |
                    | Method | `{d['payment_method']}` |
                    | Prior Attempts | {d['previous_attempts']} |
                    """)

                st.markdown("<div class='section-title'>Pipeline Decision</div>",
                            unsafe_allow_html=True)

                outcome_color = {
                    "SUCCESS": "pill-green",
                    "FAILED":  "pill-red",
                    "PENDING": "pill-yellow",
                }.get(entry["result"], "pill-blue")

                guardrail_color = "pill-green" if entry["guardrail_result"] == "APPROVED" else "pill-red"

                st.markdown(f"""
                | Step | Value |
                |---|---|
                | ML Score | `{entry['ml_score']:.4f}` |
                | AI Diagnosis | `{entry['ai_diagnosis']}` |
                | AI Recommended | `{entry['ai_recommendation']}` |
                | Guardrail | `{entry['guardrail_result']}` |
                | Action Taken | `{entry['action_taken']}` |
                | Outcome | `{entry['result']}` |
                | Event ID | `{entry['event_id']}` |
                | Timestamp | `{entry['timestamp']}` |
                """)

            with right:
                st.markdown("<div class='section-title'>Outcome Summary</div>",
                            unsafe_allow_html=True)

                outcome_emoji = {"SUCCESS": "✅", "FAILED": "❌", "PENDING": "⏳"}.get(entry["result"], "❓")
                st.markdown(f"""
                <div class='kpi-card' style='margin-bottom:16px;'>
                    <div class='kpi-label'>Final Outcome</div>
                    <div class='kpi-value'>{outcome_emoji} {entry['result']}</div>
                    <div class='kpi-sub'>Action: {entry['action_taken']}</div>
                </div>
                <div class='kpi-card'>
                    <div class='kpi-label'>ML Recovery Probability</div>
                    <div class='kpi-value'>{entry['ml_score']:.1%}</div>
                    <div class='kpi-sub'>Guardrail: {entry['guardrail_result']}</div>
                </div>
                """, unsafe_allow_html=True)

                # ML score gauge
                st.markdown("<br>**ML Recovery Score**", unsafe_allow_html=True)
                st.progress(float(entry["ml_score"]))
