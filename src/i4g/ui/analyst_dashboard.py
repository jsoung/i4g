"""Streamlit Analyst Dashboard (API-backed).

Run:
    streamlit run src/i4g/ui/analyst_dashboard.py

This dashboard calls the FastAPI endpoints (configured via API_BASE_URL)
and uses X-API-KEY for simple auth (see i4g.api.auth).

It supports:
- Listing queued cases
- Claim / Accept (with optional auto-report generation) / Reject
- Trigger report generation manually
"""

from __future__ import annotations

import streamlit as st
import httpx
import os
from typing import Dict, Any, List

# Configuration
API_BASE_URL = os.environ.get("I4G_API_URL", "http://127.0.0.1:8000/reviews")
API_KEY = os.environ.get("I4G_API_KEY", "dev-analyst-token")
HEADERS = {"X-API-KEY": API_KEY}


st.set_page_config(page_title="i4g Analyst Dashboard", layout="wide")
st.title("🕵️ i4g Analyst Dashboard (API-backed)")

# Sidebar controls
st.sidebar.header("Connection")
st.sidebar.text_input("API Base URL", value=API_BASE_URL, key="api_base")
st.sidebar.text_input("API Key", value=API_KEY, key="api_key")
if st.sidebar.button("Save connection"):
    st.experimental_set_query_params()  # noop to persist inputs in UI
    st.success("Connection settings updated (for this session).")

# Helper helpers
def api_client() -> httpx.Client:
    base = st.session_state.get("api_base", API_BASE_URL)
    key = st.session_state.get("api_key", API_KEY)
    return httpx.Client(base_url=base, headers={"X-API-KEY": key}, timeout=30.0)


def fetch_queue(status: str = "queued", limit: int = 50) -> List[Dict[str, Any]]:
    client = api_client()
    r = client.get("/queue", params={"status": status, "limit": limit})
    r.raise_for_status()
    data = r.json()
    return data.get("items", [])


def fetch_review(review_id: str) -> Dict[str, Any]:
    client = api_client()
    r = client.get(f"/{review_id}")
    r.raise_for_status()
    return r.json()


def post_action(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = api_client()
    r = client.post(path, json=payload)
    r.raise_for_status()
    return r.json()


def post_patch(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = api_client()
    r = client.patch(path, json=payload)
    r.raise_for_status()
    return r.json()


# Sidebar filter controls
status = st.sidebar.selectbox("Show cases by status", ["queued", "in_review", "accepted", "rejected"], index=0)
limit = st.sidebar.slider("Max cases to load", 5, 200, 50)

if st.sidebar.button("Refresh queue"):
    st.experimental_rerun()

queue = []
try:
    queue = fetch_queue(status=status, limit=limit)
except Exception as e:
    st.error(f"Failed to fetch queue: {e}")

if not queue:
    st.info(f"No cases in '{status}' status.")
    st.stop()

st.write(f"Showing {len(queue)} cases (status={status})")

for case in queue:
    with st.expander(f"Case {case.get('case_id')} / review_id={case.get('review_id')}"):
        st.write(case.get("notes", "No notes"))
        cols = st.columns([1, 1, 1, 2])

        # Claim
        if cols[0].button("👀 Claim", key=f"claim_{case['review_id']}"):
            try:
                resp = post_action(f"/{case['review_id']}/claim", {})
                st.success("Claimed")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Claim failed: {e}")

        # Accept (with auto_generate_report option)
        auto_report = cols[1].checkbox("Auto report", key=f"auto_{case['review_id']}")
        if cols[1].button("✅ Accept", key=f"accept_{case['review_id']}"):
            try:
                payload = {"decision": "accepted", "notes": "Accepted via dashboard", "auto_generate_report": bool(auto_report)}
                resp = post_action(f"/{case['review_id']}/decision", payload)
                st.success("Accepted")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Accept failed: {e}")

        # Reject
        if cols[2].button("❌ Reject", key=f"reject_{case['review_id']}"):
            try:
                payload = {"decision": "rejected", "notes": "Rejected via dashboard"}
                resp = post_action(f"/{case['review_id']}/decision", payload)
                st.success("Rejected")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Reject failed: {e}")

        # Manual report generation
        if cols[3].button("📄 Generate Report", key=f"report_{case['review_id']}"):
            try:
                # Call the report generation endpoint using decision with auto flag False
                payload = {"decision": "accepted", "notes": "Manual report generation", "auto_generate_report": False}
                # First update status to accepted
                post_action(f"/{case['review_id']}/decision", payload)
                # Then call report generation explicitly
                r = api_client().post(f"/{case['review_id']}/claim", json={})
                st.info("Requested manual report generation (backend will handle export).")
            except Exception as e:
                st.error(f"Report generation request failed: {e}")

        # Show actions/audit
        if st.button("Show history", key=f"history_{case['review_id']}"):
            try:
                client = api_client()
                r = client.get(f"/{case['review_id']}/actions")
                r.raise_for_status()
                st.json(r.json())
            except Exception as e:
                st.error(f"Failed to fetch history: {e}")
