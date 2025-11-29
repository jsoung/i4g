"""Discovery search panel for the Streamlit dashboard."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import streamlit as st

from i4g.ui.api import perform_vertex_search


def render_discovery_engine_panel() -> None:
    """Render the Discovery search controls and results."""

    st.divider()
    st.subheader("🌐 Discovery (Vertex AI) search")

    with st.form("vertex_search_form"):
        st.text_input(
            "Query",
            key="vertex_search_query",
            placeholder="wallet address flagged withdrawal",
        )
        col_project, col_location, col_page = st.columns([1.2, 1.2, 0.8])
        with col_project:
            st.text_input("Project", key="vertex_search_project")
            st.text_input("Data store ID", key="vertex_search_data_store")
        with col_location:
            st.text_input("Location", key="vertex_search_location", help="Use 'global' for worldwide indices.")
            st.text_input("Serving config ID", key="vertex_search_serving_config")
        with col_page:
            st.number_input("Page size", min_value=1, max_value=50, step=1, key="vertex_search_page_size")
        st.text_input(
            "Filter expression",
            key="vertex_search_filter",
            help='Discovery filter syntax, e.g. tags: ANY("account-security").',
        )
        st.text_area(
            "Boost JSON",
            key="vertex_search_boost_json",
            help="Optional SearchRequest.BoostSpec payload for ranking experiments.",
        )
        vertex_submitted = st.form_submit_button("Run Discovery search", width="stretch")

    show_raw_toggle = st.checkbox("Show raw JSON for each result", key="vertex_search_show_raw")

    if vertex_submitted:
        query_value = (st.session_state.get("vertex_search_query") or "").strip()
        project_value = (st.session_state.get("vertex_search_project") or "").strip()
        location_value = (st.session_state.get("vertex_search_location") or "").strip() or "global"
        data_store_value = (st.session_state.get("vertex_search_data_store") or "").strip()
        serving_config_value = (st.session_state.get("vertex_search_serving_config") or "").strip() or "default_search"
        page_size_value = int(st.session_state.get("vertex_search_page_size") or 5)
        filter_value = (st.session_state.get("vertex_search_filter") or "").strip()
        boost_value = (st.session_state.get("vertex_search_boost_json") or "").strip()

        params: Dict[str, Optional[str] | int] = {
            "query": query_value,
            "project": project_value,
            "location": location_value,
            "data_store_id": data_store_value,
            "serving_config_id": serving_config_value,
            "page_size": page_size_value,
            "filter_expression": filter_value or None,
            "boost_json": boost_value or None,
        }

        st.session_state["vertex_search_params"] = params

        if not query_value:
            st.session_state["vertex_search_error"] = "Enter a query string."
            st.session_state["vertex_search_results"] = None
        elif not project_value:
            st.session_state["vertex_search_error"] = "Provide the Google Cloud project ID."
            st.session_state["vertex_search_results"] = None
        elif not data_store_value:
            st.session_state["vertex_search_error"] = "Provide the Discovery data store ID."
            st.session_state["vertex_search_results"] = None
        else:
            try:
                with st.spinner("Querying Discovery..."):
                    vertex_results = perform_vertex_search(params)
            except RuntimeError as exc:
                st.session_state["vertex_search_results"] = None
                st.session_state["vertex_search_error"] = str(exc)
            else:
                st.session_state["vertex_search_results"] = vertex_results
                st.session_state["vertex_search_error"] = None

    vertex_error = st.session_state.get("vertex_search_error")
    if vertex_error:
        st.error(f"Discovery search failed: {vertex_error}")

    vertex_results_state: Optional[List[Dict[str, Any]]] = st.session_state.get("vertex_search_results")
    vertex_params = st.session_state.get("vertex_search_params") or {}

    if vertex_results_state:
        st.subheader("🔎 Discovery results")
        st.caption(
            f"{len(vertex_results_state)} result(s) · page size {vertex_params.get('page_size', 'n/a')} · "
            f"data store {vertex_params.get('data_store_id', 'n/a')}"
        )
        raw_download = json.dumps([item["raw"] for item in vertex_results_state], indent=2)
        st.download_button(
            label="Download raw JSON",
            data=raw_download,
            file_name="vertex_search_results.json",
            mime="application/json",
            key="vertex_search_download",
        )
        for item in vertex_results_state:
            header_text = f"#{item['rank']} — {item['document_id']}"
            result_label = item.get("label")
            if result_label:
                header_text += f" (label: {result_label})"
            st.markdown(f"**{header_text}**")

            summary = item.get("summary")
            if summary:
                st.write(summary)

            meta_parts = []
            source_value = item.get("source")
            if source_value:
                meta_parts.append(f"source={source_value}")
            index_type_value = item.get("index_type")
            if index_type_value and index_type_value != source_value:
                meta_parts.append(f"index_type={index_type_value}")
            if meta_parts:
                st.caption(" · ".join(meta_parts))

            tags = item.get("tags") or []
            if tags:
                st.caption("Tags: " + ", ".join(tags))

            rank_signals = item.get("rank_signals") or {}
            if rank_signals:
                highlight = []
                for key, label_text in (
                    ("semanticSimilarityScore", "semantic"),
                    ("keywordSimilarityScore", "keyword"),
                    ("topicalityRank", "topicality"),
                ):
                    value = rank_signals.get(key)
                    if value is not None:
                        highlight.append(f"{label_text}={value}")
                if highlight:
                    st.caption(" · ".join(highlight))
                with st.expander("Rank signals", expanded=False):
                    st.json(rank_signals)

            struct_data = item.get("struct") or {}
            if struct_data:
                with st.expander("Structured fields", expanded=False):
                    st.json(struct_data)

            if show_raw_toggle:
                with st.expander("Raw response", expanded=False):
                    st.json(item["raw"])

            st.markdown("---")
    elif vertex_results_state == [] and vertex_params:
        st.info("Discovery returned no matches. Try adjusting the query or filters.")
