"""
Streamlit prototype: Analyst Review Dashboard (M6.2 Part B)

Usage:
    streamlit run adhoc/analyst_dashboard_demo.py
"""

import streamlit as st

from i4g.store.review_store import ReviewStore
from i4g.worker.tasks import generate_report_for_case

st.set_page_config(page_title="i4g Analyst Dashboard", layout="wide")


def rerun_dashboard() -> None:
    """Compatibility wrapper for Streamlit rerun across versions."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


# Initialize or reuse local store
store = ReviewStore()

st.title("🕵️ i4g Analyst Review Dashboard")
st.caption("Experimental prototype – crypto & romance scam case triage")

# ------------------------------
# Sidebar: Filters & controls
# ------------------------------
st.sidebar.header("Queue Filter")
status = st.sidebar.selectbox("Show cases by status", ["queued", "in_review", "accepted", "rejected"], index=0)
refresh = st.sidebar.button("🔄 Refresh queue")

# ------------------------------
# Load review queue
# ------------------------------
queue = store.get_queue(status=status)
if not queue:
    st.info(f"No cases currently in '{status}' state.")
    st.stop()

st.success(f"Loaded {len(queue)} case(s).")

# ------------------------------
# Display queue
# ------------------------------
for case in queue:
    with st.expander(f"Case {case['case_id']} ({case['priority']}) – Status: {case['status']}"):
        st.write(case.get("notes", ""))
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

        with col1:
            if st.button("👀 Claim", key=f"claim_{case['review_id']}"):
                store.update_status(case["review_id"], status="in_review", notes="Claimed via dashboard")
                store.log_action(case["review_id"], actor="dashboard", action="claimed")
                st.toast("Case claimed for review.")
                rerun_dashboard()

        with col2:
            if st.button("✅ Accept", key=f"accept_{case['review_id']}"):
                store.update_status(case["review_id"], status="accepted", notes="Accepted via dashboard")
                store.log_action(case["review_id"], actor="dashboard", action="accepted")
                st.toast("Case accepted.")
                rerun_dashboard()

        with col3:
            if st.button("❌ Reject", key=f"reject_{case['review_id']}"):
                store.update_status(case["review_id"], status="rejected", notes="Rejected via dashboard")
                store.log_action(case["review_id"], actor="dashboard", action="rejected")
                st.toast("Case rejected.")
                rerun_dashboard()

        with col4:
            if st.button("📄 Generate Report", key=f"report_{case['review_id']}"):
                st.write("Generating report...")
                doc_id = generate_report_for_case(case["review_id"], store=store)
                st.toast(f"Report generation result: {doc_id}")

# ------------------------------
# Footer
# ------------------------------
st.divider()
st.caption("© Intelligence for Good – Experimental prototype (M6.2 Part B)")
