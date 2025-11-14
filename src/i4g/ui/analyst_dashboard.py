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

import json
from typing import Any, Dict, List

import streamlit as st

import i4g.ui.api as ui_api
from i4g.ui.state import ensure_session_defaults
from i4g.ui.views import render_discovery_engine_panel

# Configuration
TAG_PAL = [
    "#E0BBE4",
    "#957DAD",
    "#D291BC",
    "#FEC8D8",
    "#FFDFD3",
    "#C5E1A5",
    "#B2DFDB",
]


def run_search(params: Dict[str, Any], offset: int) -> None:
    try:
        st.session_state["case_reviews"] = {}
        payload = ui_api.search_cases_api(
            text=params.get("text"),
            classification=params.get("classification"),
            case_id=params.get("case_id"),
            vector_limit=params["vector_limit"],
            structured_limit=params["structured_limit"],
            page_size=params["page_size"],
            offset=offset,
        )
        results = payload.get("results", [])
        st.session_state["search_results"] = results
        st.session_state["search_error"] = None
        st.session_state["search_offset"] = payload.get("offset", offset)
        st.session_state["search_more_available"] = len(results) == params["page_size"]
        st.session_state["search_meta"] = {
            "total": payload.get("total"),
            "vector_hits": payload.get("vector_hits"),
            "structured_hits": payload.get("structured_hits"),
            "search_id": payload.get("search_id"),
        }

        try:
            history_payload = ui_api.fetch_search_history(limit=st.session_state.get("history_limit", 10))
            st.session_state["search_history"] = history_payload.get("events", [])
            st.session_state["search_history_error"] = None
        except Exception as exc:
            st.session_state["search_history_error"] = str(exc)

        try:
            saved_payload = ui_api.fetch_saved_searches(limit=25)
            st.session_state["saved_searches"] = saved_payload.get("items", [])
            st.session_state["saved_search_error"] = None
        except Exception as exc:
            st.session_state["saved_search_error"] = str(exc)
    except Exception as exc:
        st.session_state["search_results"] = None
        st.session_state["search_error"] = str(exc)
        st.session_state["search_more_available"] = False


def _execute_saved_search(saved_id: str, params: Dict[str, Any]) -> None:
    st.session_state["active_saved_search_id"] = saved_id
    st.session_state["search_text_input"] = params.get("text", "") or ""
    st.session_state["search_class_input"] = params.get("classification", "") or ""
    st.session_state["search_case_input"] = params.get("case_id", "") or ""
    st.session_state["search_vector_limit_slider"] = params.get("vector_limit", 5) or 5
    st.session_state["search_structured_limit_slider"] = params.get("structured_limit", 5) or 5
    st.session_state["search_page_size_slider"] = params.get("page_size", 5) or 5
    st.session_state["search_params"] = params
    offset = params.get("offset", 0)
    st.session_state["search_offset"] = offset
    run_search(params, offset=offset)
    st.rerun()


def _tag_badge(tag: str) -> str:
    color = TAG_PAL[hash(tag) % len(TAG_PAL)]
    return f"<span style='background:{color}; padding:2px 6px; border-radius:6px; margin-right:4px;'>{tag}</span>"


st.set_page_config(page_title="i4g Analyst Dashboard", layout="wide")
st.title("🕵️ i4g Analyst Dashboard (API-backed)")

# Sidebar controls
ensure_session_defaults()

st.sidebar.header("Connection")
st.sidebar.text_input("API Base URL", key="api_base")
st.sidebar.text_input("API Key", key="api_key")
if st.sidebar.button("Save connection"):
    st.experimental_set_query_params()  # noop to persist inputs in UI
    st.success("Connection settings updated (for this session).")

with st.sidebar.form("case_search_form"):
    st.markdown("### Search cases")
    search_text = st.text_input("Text query", key="search_text_input")
    search_classification = st.text_input("Classification filter", key="search_class_input")
    search_case_id = st.text_input("Case ID filter", key="search_case_input")
    search_vector_limit = st.slider(
        "Vector results",
        1,
        20,
        st.session_state["search_vector_limit_value"],
        key="search_vector_limit_slider",
    )
    search_structured_limit = st.slider(
        "Structured results",
        1,
        20,
        st.session_state["search_structured_limit_value"],
        key="search_structured_limit_slider",
    )
    search_page_size = st.slider(
        "Results per page",
        1,
        20,
        st.session_state["search_page_size_value"],
        key="search_page_size_slider",
    )
    save_name = st.text_input("Save as", key="save_search_name", help="Optional name to save this search")
    save_requested = st.checkbox("Save search", key="save_search_checkbox")
    update_existing = st.checkbox(
        "Update current saved search",
        key="update_saved_search_checkbox",
        help="When checked, overwrite the active saved search.",
        disabled=st.session_state.get("active_saved_search_id") is None,
    )
    preview_enabled = st.checkbox(
        "Preview before running saved/history searches",
        value=st.session_state.get("preview_enabled", True),
        key="preview_toggle",
        help="Show the parameters in a dialog before executing.",
    )
    search_submitted = st.form_submit_button("Search")

st.session_state["search_vector_limit_value"] = st.session_state["search_vector_limit_slider"]
st.session_state["search_structured_limit_value"] = st.session_state["search_structured_limit_slider"]
st.session_state["search_page_size_value"] = st.session_state["search_page_size_slider"]
st.session_state["preview_enabled"] = preview_enabled

if st.session_state.get("pending_saved_search_preview"):
    preview = st.session_state["pending_saved_search_preview"]
    with st.container():
        st.info(f"Preview saved search: {preview.get('name') or preview.get('id')}")
        st.json(preview.get("params", {}))
        confirm_col, cancel_col = st.columns([1, 1])
        if confirm_col.button("Run saved search", key="confirm_saved_search_preview"):
            data = st.session_state.pop("pending_saved_search_preview")
            _execute_saved_search(data["id"], data["params"])
        if cancel_col.button("Cancel", key="cancel_saved_search_preview"):
            st.session_state.pop("pending_saved_search_preview", None)
            st.rerun()

if st.session_state.get("pending_history_search_preview"):
    history_preview = st.session_state["pending_history_search_preview"]
    with st.container():
        st.info(f"Preview history search: {history_preview.get('key')}")
        st.json(history_preview.get("params", {}))
        confirm_hist, cancel_hist = st.columns([1, 1])
        if confirm_hist.button("Run history search", key="confirm_history_search_preview"):
            data = st.session_state.pop("pending_history_search_preview")
            _execute_saved_search(data["key"], data["params"])
        if cancel_hist.button("Cancel", key="cancel_history_search_preview"):
            st.session_state.pop("pending_history_search_preview", None)
            st.rerun()

with st.sidebar.expander("Recent search history", expanded=False):
    history_limit = st.slider(
        "Entries to load",
        5,
        50,
        st.session_state["history_limit"],
        key="history_limit_slider",
    )
    if st.button("Refresh history", key="refresh_history_btn"):
        try:
            payload = ui_api.fetch_search_history(limit=history_limit)
            st.session_state["search_history"] = payload.get("events", [])
            st.session_state["search_history_error"] = None
            st.session_state["history_limit"] = history_limit
        except Exception as exc:
            st.session_state["search_history_error"] = str(exc)

with st.sidebar.expander("Saved searches", expanded=False):
    if st.button("Refresh saved searches", key="refresh_saved_searches_btn"):
        try:
            payload = ui_api.fetch_saved_searches(limit=25)
            st.session_state["saved_searches"] = payload.get("items", [])
            st.session_state["saved_search_error"] = None
        except Exception as exc:
            st.session_state["saved_search_error"] = str(exc)

    if st.button("Export tag presets", key="export_tag_presets_btn"):
        try:
            presets = ui_api.fetch_tag_presets()
            data = json.dumps(presets, indent=2)
            st.download_button(
                label="Download Tag Presets",
                data=data,
                file_name="tag_presets.json",
                mime="application/json",
                key="download_tag_presets",
            )
        except RuntimeError as exc:
            st.error(str(exc))
    if st.button("Share current tag filters", key="share_tag_filters_btn"):
        tags_to_share = list(st.session_state.get("tag_filters") or [])
        if not tags_to_share:
            st.warning("Select at least one tag filter before sharing.")
        else:
            preset_payload = {
                "name": ", ".join(tags_to_share) or "Preset",
                "params": {},
                "tags": tags_to_share,
            }
            try:
                ui_api.import_saved_search_api(preset_payload)
                st.success("Tag filter saved as shared preset via saved searches.")
            except RuntimeError as exc:
                st.error(str(exc))
    uploaded_file = st.file_uploader("Import saved search (.json)", type=["json"], key="saved_search_import")
    if uploaded_file is not None:
        try:
            content = uploaded_file.read()
            data = json.loads(content.decode("utf-8"))
            items = data if isinstance(data, list) else [data]
            for item in items:
                ui_api.import_saved_search_api(item)
            st.success(f"Imported {len(items)} saved search(es).")
            refreshed = ui_api.fetch_saved_searches(limit=25)
            st.session_state["saved_searches"] = refreshed.get("items", [])
            st.session_state["saved_search_error"] = None
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Failed to import saved search: {exc}")
        finally:
            uploaded_file.close()
    presets_file = st.file_uploader("Import tag presets (.json)", type=["json"], key="tag_preset_import")
    if presets_file is not None:
        try:
            content = presets_file.read()
            data = json.loads(content.decode("utf-8"))
            items = data if isinstance(data, list) else [data]
            imported = 0
            for preset in items:
                tags = preset.get("tags") or []
                if not tags:
                    continue
                if tags not in st.session_state["saved_tag_filters"]:
                    st.session_state["saved_tag_filters"].append(tags)
                    imported += 1
            st.success(f"Imported {imported} tag preset(s).")
        except Exception as exc:
            st.error(f"Failed to import tag presets: {exc}")
        finally:
            presets_file.close()
    saved_error = st.session_state.get("saved_search_error")
    if saved_error:
        st.error(saved_error)

    saved_items = st.session_state.get("saved_searches") or []
    all_tags = sorted({tag for item in saved_items for tag in (item.get("tags") or [])})

    if "saved_search_tag_filter" not in st.session_state:
        st.session_state["saved_search_tag_filter"] = list(st.session_state.get("tag_filters") or [])

    if all_tags:
        cols_tag = st.columns([2, 1])
        selected_tags = cols_tag[0].multiselect(
            "Filter by tag",
            options=all_tags,
            default=st.session_state.get("saved_search_tag_filter", []),
            key="saved_search_tag_filter",
            help="Narrow saved searches by tag label(s).",
        )
        st.session_state["tag_filters"] = set(selected_tags)
        with cols_tag[1]:
            st.write("")
            if st.button("Clear filters", key="clear_tag_filters", use_container_width=True):
                st.session_state["tag_filters"] = set()
                st.session_state["saved_search_tag_filter"] = []
                selected_tags = []
        if st.button("Save preset", key="save_tag_filter_preset", disabled=not selected_tags):
            normalized = sorted({tag.strip() for tag in selected_tags})
            presets = st.session_state["saved_tag_filters"]
            if normalized not in presets:
                presets.append(normalized)
                st.success("Preset saved for this session.")
        preset_labels = [", ".join(tags) for tags in st.session_state["saved_tag_filters"]]
        if preset_labels:
            preset_choice = st.selectbox(
                "Load preset",
                options=["(none)"] + preset_labels,
                key="tag_filter_preset_select",
                help="Apply a previously saved tag combination.",
            )
            if preset_choice != "(none)":
                idx = preset_labels.index(preset_choice)
                chosen = st.session_state["saved_tag_filters"][idx]
                st.session_state["tag_filters"] = set(chosen)
                st.session_state["saved_search_tag_filter"] = list(chosen)
    else:
        st.caption("Apply tags to saved searches to enable filtering and presets.")

    active_filters = set(st.session_state.get("tag_filters") or [])
    selected_ids = st.session_state["bulk_selected_saved_searches"]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    filtered_items: List[Dict[str, Any]] = []

    for saved in saved_items:
        tags = saved.get("tags") or []
        filter_tags = tags or ["untagged"]
        if active_filters and not active_filters.intersection(filter_tags):
            continue
        filtered_items.append(saved)
        for tag in filter_tags:
            grouped.setdefault(tag, []).append(saved)

    if filtered_items:
        bulk_cols = st.columns([1.2, 1.2, 0.8])
        if bulk_cols[0].button("Select all filtered", key="bulk_select_all_filtered"):
            for item in filtered_items:
                search_id = item.get("search_id")
                if not search_id:
                    continue
                selected_ids.add(search_id)
                st.session_state[f"saved_select_{search_id}"] = True
        if bulk_cols[1].button("Clear selection", key="bulk_clear_selection"):
            selected_ids.clear()
            for item in saved_items:
                search_id = item.get("search_id")
                if not search_id:
                    continue
                st.session_state[f"saved_select_{search_id}"] = False
        bulk_cols[2].markdown(f"**Selected:** {len(selected_ids)}")
    else:
        st.info("No saved searches match the current tag filters.")

    if selected_ids:
        with st.expander(f"Bulk tag update ({len(selected_ids)} selected)", expanded=True):
            st.caption("IDs: " + ", ".join(list(selected_ids)[:5]) + ("..." if len(selected_ids) > 5 else ""))
            add_tags_raw = st.text_input("Add tags (comma separated)", key="bulk_tags_add")
            remove_tags_raw = st.text_input("Remove tags", key="bulk_tags_remove")
            replace_tags_raw = st.text_input(
                "Replace tags entirely",
                key="bulk_tags_replace",
                help="When provided, replaces the existing tags with this list.",
            )
            apply_cols = st.columns([1, 1])
            if apply_cols[0].button("Apply bulk tag update", key="apply_bulk_tag_update"):
                add_tags = ui_api._parse_tags(add_tags_raw)
                remove_tags = ui_api._parse_tags(remove_tags_raw)
                replace_tags = ui_api._parse_tags(replace_tags_raw)
                if not any([add_tags, remove_tags, replace_tags]):
                    st.warning("Provide tags to add, remove, or replace before applying.")
                else:
                    try:
                        result = ui_api.bulk_update_saved_search_tags(
                            list(selected_ids),
                            add=add_tags or None,
                            remove=remove_tags or None,
                            replace=replace_tags or None,
                        )
                        updated = result.get("updated", len(selected_ids))
                        st.success(f"Updated {updated} saved search(es).")
                        selected_ids.clear()
                        for item in saved_items:
                            search_id = item.get("search_id")
                            if not search_id:
                                continue
                            st.session_state[f"saved_select_{search_id}"] = False
                        st.session_state["bulk_tags_add"] = ""
                        st.session_state["bulk_tags_remove"] = ""
                        st.session_state["bulk_tags_replace"] = ""
                        refreshed = ui_api.fetch_saved_searches(limit=25)
                        st.session_state["saved_searches"] = refreshed.get("items", [])
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))
            if apply_cols[1].button("Cancel bulk edit", key="cancel_bulk_tag_update"):
                selected_ids.clear()
                st.session_state["bulk_tags_add"] = ""
                st.session_state["bulk_tags_remove"] = ""
                st.session_state["bulk_tags_replace"] = ""
                for item in saved_items:
                    search_id = item.get("search_id")
                    if not search_id:
                        continue
                    st.session_state[f"saved_select_{search_id}"] = False

    for tag in sorted(grouped):
        items = grouped[tag]
        st.markdown(f"#### Tag: `{tag}`")
        for saved in items:
            params = saved.get("params", {}) or {}
            name = saved.get("name", saved.get("search_id"))
            saved_id = saved.get("search_id")
            is_favorite = bool(saved.get("favorite"))
            tag_badge = " ".join(_tag_badge(t) for t in (saved.get("tags") or []))
            owner_badge = "(shared)" if saved.get("owner") is None else f"(owner: {saved.get('owner')})"
            st.markdown(f"**{name}** {owner_badge} {tag_badge}", unsafe_allow_html=True)
            (
                col_select,
                col_fav,
                col_load,
                col_info,
                col_share,
                col_download,
                col_delete,
            ) = st.columns([0.6, 0.5, 1, 1, 1, 1, 1])
            is_selected = saved_id in selected_ids
            new_selected = col_select.checkbox(
                "Select",
                value=is_selected,
                key=f"saved_select_{saved_id}",
            )
            if new_selected and not is_selected:
                selected_ids.add(saved_id)
            elif not new_selected and is_selected:
                selected_ids.discard(saved_id)

            fav_label = "★" if is_favorite else "☆"
            if col_fav.button(fav_label, key=f"fav_saved_{saved_id}"):
                try:
                    ui_api.patch_saved_search(saved_id, favorite=not is_favorite)
                    st.success(f"{'Pinned' if not is_favorite else 'Unpinned'} '{name}'")
                    refreshed = ui_api.fetch_saved_searches(limit=25)
                    st.session_state["saved_searches"] = refreshed.get("items", [])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to toggle favorite: {exc}")
            if col_load.button("Run", key=f"run_saved_{saved_id}"):
                if st.session_state.get("preview_enabled", True):
                    st.session_state["pending_saved_search_preview"] = {
                        "id": saved_id,
                        "params": params,
                        "name": name,
                    }
                    st.rerun()
                else:
                    _execute_saved_search(saved_id, params)
            with col_info.expander("Details / Rename", expanded=False):
                st.json(params)
                st.caption(f"Owner: {saved.get('owner', 'shared')} · Created {saved.get('created_at', 'unknown')}")
                current_tags = saved.get("tags") or []
                tag_input = st.text_input(
                    "Tags (comma separated)",
                    ", ".join(current_tags),
                    key=f"tags_{saved_id}",
                )
                new_name = st.text_input("Rename", value=name, key=f"rename_{saved_id}")
                if st.button("Apply rename", key=f"apply_rename_{saved_id}"):
                    try:
                        tags_list = ui_api._parse_tags(tag_input)
                        ui_api.patch_saved_search(saved_id, name=new_name, tags=tags_list)
                        st.success(f"Renamed to '{new_name}'")
                        refreshed = ui_api.fetch_saved_searches(limit=25)
                        st.session_state["saved_searches"] = refreshed.get("items", [])
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Failed to rename saved search: {exc}")
            if saved.get("owner"):
                if col_share.button("Share", key=f"share_saved_{saved_id}"):
                    try:
                        resp = ui_api.share_saved_search(saved_id)
                        st.success("Shared search published to team scope")
                        refreshed = ui_api.fetch_saved_searches(limit=25)
                        st.session_state["saved_searches"] = refreshed.get("items", [])
                        st.session_state["active_saved_search_id"] = resp.get("search_id")
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Failed to share search: {exc}")
            else:
                col_share.write(" ")
            if col_download.button("Export", key=f"export_saved_{saved_id}"):
                try:
                    record = ui_api.export_saved_search(saved_id)
                    data = json.dumps(record, indent=2)
                    st.download_button(
                        label="Download JSON",
                        data=data,
                        file_name=f"saved_search_{saved_id}.json",
                        mime="application/json",
                        key=f"download_btn_{saved_id}",
                    )
                except RuntimeError as exc:
                    st.error(str(exc))
            if col_delete.button("Delete", key=f"delete_saved_{saved_id}"):
                try:
                    ui_api.delete_saved_search(saved_id)
                    st.success(f"Deleted saved search '{name}'")
                    updated = ui_api.fetch_saved_searches(limit=25)
                    st.session_state["saved_searches"] = updated.get("items", [])
                    if st.session_state.get("active_saved_search_id") == saved_id:
                        st.session_state["active_saved_search_id"] = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to delete saved search: {exc}")

st.session_state["history_limit"] = st.session_state.get("history_limit_slider", st.session_state["history_limit"])


render_discovery_engine_panel()


if search_submitted:
    params = {
        "text": (search_text.strip() or None) if search_text else None,
        "classification": ((search_classification.strip() or None) if search_classification else None),
        "case_id": (search_case_id.strip() or None) if search_case_id else None,
        "vector_limit": st.session_state["search_vector_limit_value"],
        "structured_limit": st.session_state["search_structured_limit_value"],
        "page_size": st.session_state["search_page_size_value"],
    }
    if update_existing and st.session_state.get("active_saved_search_id"):
        params["search_id"] = st.session_state["active_saved_search_id"]
    st.session_state["search_params"] = params
    st.session_state["search_offset"] = 0
    run_search(params, offset=0)
    if save_requested and save_name.strip():
        try:
            active_id = st.session_state.get("active_saved_search_id") if update_existing else None
            current_favorite = None
            if active_id:
                for item in st.session_state.get("saved_searches", []):
                    if item.get("search_id") == active_id:
                        current_favorite = bool(item.get("favorite"))
                        break
            response = ui_api.save_search(
                save_name.strip(),
                params,
                search_id=active_id,
                favorite=current_favorite,
            )
            st.success(f"Saved search '{save_name.strip()}'")
            payload = ui_api.fetch_saved_searches(limit=25)
            st.session_state["saved_searches"] = payload.get("items", [])
            st.session_state["saved_search_error"] = None
            st.session_state["active_saved_search_id"] = response.get("search_id")
        except Exception as exc:
            message = str(exc)
            if "Saved search name already exists" in message:
                st.error(message)
            else:
                st.error(f"Failed to save search: {message}")
    elif not update_existing:
        st.session_state["active_saved_search_id"] = None


# Sidebar filter controls
status = st.sidebar.selectbox("Show cases by status", ["queued", "in_review", "accepted", "rejected"], index=0)
limit = st.sidebar.slider("Max cases to load", 5, 200, 50)

if st.sidebar.button("Refresh queue"):
    st.rerun()

search_error = st.session_state.get("search_error")
if search_error:
    st.error(f"Search failed: {search_error}")

search_params = st.session_state.get("search_params")
current_offset = st.session_state.get("search_offset", 0)
page_size = search_params["page_size"] if search_params else None
meta = st.session_state.get("search_meta") or {}
if search_params and page_size:
    range_start = current_offset + 1
    range_end = current_offset + len(st.session_state.get("search_results") or [])
    total = meta.get("total")
    if total is not None:
        st.caption(
            f"Showing results {range_start}–{range_end} of {total} | "
            f"vector hits: {meta.get('vector_hits', 'n/a')} | "
            f"structured hits: {meta.get('structured_hits', 'n/a')}"
        )
    else:
        st.caption(f"Showing results {range_start}–{range_end} (page size {page_size})")

    nav_prev, nav_next = st.columns(2)
    if nav_prev.button("◀ Prev", key="search_prev_btn", disabled=current_offset <= 0):
        new_offset = max(0, current_offset - page_size)
        st.session_state["search_offset"] = new_offset
        run_search(search_params, offset=new_offset)
    st.rerun()

    if nav_next.button(
        "Next ▶",
        key="search_next_btn",
        disabled=not st.session_state.get("search_more_available"),
    ):
        new_offset = current_offset + page_size
        st.session_state["search_offset"] = new_offset
        run_search(search_params, offset=new_offset)
    st.rerun()

search_results = st.session_state.get("search_results") or []
if search_results:
    st.subheader("🔍 Search results")
    search_meta = st.session_state.get("search_meta") or {}
    search_id = search_meta.get("search_id")
    if search_id:
        st.caption(f"Search ID: {search_id}")

    csv_button = st.button("⬇️ Export current page", key="export_search_csv")
    if csv_button:
        try:
            import csv
            from io import StringIO

            output = StringIO()
            fieldnames = ["case_id", "score", "sources", "vector", "record"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for result in search_results:
                writer.writerow(
                    {
                        "case_id": result.get("case_id"),
                        "score": result.get("score"),
                        "sources": ",".join(result.get("sources", [])),
                        "vector": json.dumps(result.get("vector", {})),
                        "record": json.dumps(result.get("record", {})),
                    }
                )

            st.download_button(
                label="Download CSV",
                data=output.getvalue(),
                file_name=f"search_results_{search_id or 'page'}.csv",
                mime="text/csv",
                key="download_search_csv",
            )
        except Exception as exc:
            st.error(f"Failed to export search results: {exc}")
    for result in search_results:
        case_id = result.get("case_id", "Unknown case")
        sources = ", ".join(result.get("sources", []))
        score = result.get("score")
        score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
        st.markdown(f"**Case {case_id}** — score: {score_txt} · sources: {sources or 'n/a'}")

        record = result.get("record")
        vector_hit = result.get("vector")
        case_reviews = st.session_state["case_reviews"].get(case_id)

        if record:
            st.markdown("Structured record:")
            st.json(record)
        if vector_hit:
            st.markdown("Semantic match:")
            st.json(vector_hit)

        if st.button("Show queue entries", key=f"show_queue_{case_id}"):
            try:
                payload = ui_api.fetch_case_reviews(
                    case_id,
                    limit=st.session_state.get("search_structured_limit_value", 5),
                )
                st.session_state["case_reviews"][case_id] = payload.get("reviews", [])
                case_reviews = st.session_state["case_reviews"].get(case_id)
            except Exception as exc:
                st.error(f"Failed to load queue entries for {case_id}: {exc}")
                case_reviews = None

        if case_reviews:
            st.markdown("Queue entries:")
            for review in case_reviews:
                review_id = review.get("review_id")
                status = review.get("status")
                notes = review.get("notes", "")
                st.write(f"- `review_id={review_id}` · status={status} · notes={notes or '—'}")
                action_cols = st.columns(3)

                if action_cols[0].button("Claim", key=f"claim_search_{review_id}"):
                    try:
                        ui_api.post_action(f"/{review_id}/claim", {})
                        st.success(f"Review {review_id} claimed.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to claim {review_id}: {exc}")

                if action_cols[1].button("Accept", key=f"accept_search_{review_id}"):
                    try:
                        ui_api.post_action(
                            f"/{review_id}/decision",
                            {
                                "decision": "accepted",
                                "notes": "Accepted from search panel",
                                "auto_generate_report": False,
                            },
                        )
                        st.success(f"Review {review_id} accepted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to accept {review_id}: {exc}")

                if action_cols[2].button("Reject", key=f"reject_search_{review_id}"):
                    try:
                        ui_api.post_action(
                            f"/{review_id}/decision",
                            {
                                "decision": "rejected",
                                "notes": "Rejected from search panel",
                            },
                        )
                        st.warning(f"Review {review_id} rejected.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to reject {review_id}: {exc}")

        st.divider()

history_error = st.session_state.get("search_history_error")
if history_error:
    st.error(f"Failed to load search history: {history_error}")

history_events = st.session_state.get("search_history") or []
if history_events:
    st.subheader("🕘 Recent search history")
    for event in history_events:
        payload = event.get("payload", {})
        timestamp = event.get("created_at", "unknown time")
        actor = event.get("actor", "unknown")
        summary = payload.get("text") or payload.get("case_id") or "(no query)"
        search_key = payload.get("search_id", event.get("action_id"))
        tags = payload.get("tags") or []
        tag_badge = "".join(f"[`{t}`]" for t in tags)
        cols = st.columns([0.6, 0.4])
        cols[0].markdown(
            f"`{search_key}` · {timestamp} · {actor} · query: `{summary}` {' '.join(_tag_badge(t) for t in tags)}",
            unsafe_allow_html=True,
        )
        if cols[1].button("Run", key=f"run_history_{search_key}"):
            params = {
                "text": payload.get("text"),
                "classification": payload.get("classification"),
                "case_id": payload.get("case_id"),
                "vector_limit": payload.get("vector_limit", st.session_state["search_vector_limit_value"]),
                "structured_limit": payload.get(
                    "structured_limit",
                    st.session_state["search_structured_limit_value"],
                ),
                "page_size": payload.get("page_size", st.session_state["search_page_size_value"]),
            }
            if st.session_state.get("preview_enabled", True):
                st.session_state["pending_history_search_preview"] = {
                    "key": search_key,
                    "params": params,
                }
                st.rerun()
            else:
                _execute_saved_search(search_key, params)

queue = []
try:
    queue = ui_api.fetch_queue(status=status, limit=limit)
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
                resp = ui_api.post_action(f"/{case['review_id']}/claim", {})
                st.success("Claimed")
                st.rerun()
            except Exception as e:
                st.error(f"Claim failed: {e}")

        # Accept (with auto_generate_report option)
        auto_report = cols[1].checkbox("Auto report", key=f"auto_{case['review_id']}")
        if cols[1].button("✅ Accept", key=f"accept_{case['review_id']}"):
            try:
                payload = {
                    "decision": "accepted",
                    "notes": "Accepted via dashboard",
                    "auto_generate_report": bool(auto_report),
                }
                resp = ui_api.post_action(f"/{case['review_id']}/decision", payload)
                st.success("Accepted")
                st.rerun()
            except Exception as e:
                st.error(f"Accept failed: {e}")

        # Reject
        if cols[2].button("❌ Reject", key=f"reject_{case['review_id']}"):
            try:
                payload = {"decision": "rejected", "notes": "Rejected via dashboard"}
                resp = ui_api.post_action(f"/{case['review_id']}/decision", payload)
                st.success("Rejected")
                st.rerun()
            except Exception as e:
                st.error(f"Reject failed: {e}")

        # Manual report generation
        if cols[3].button("📄 Generate Report", key=f"report_{case['review_id']}"):
            try:
                # Ensure the case is marked accepted before triggering report generation
                ui_api.post_action(
                    f"/{case['review_id']}/decision",
                    {
                        "decision": "accepted",
                        "notes": "Manual report generation",
                        "auto_generate_report": False,
                    },
                )

                client = ui_api.api_client()
                response = client.post("/reports/generate")
                response.raise_for_status()
                payload = response.json()
                task_id = payload.get("task_id")

                if task_id:
                    st.success(f"Report generation started (task_id={task_id}).")
                    st.caption("Use the Tasks tab or API to poll status.")
                else:
                    st.success("Report generation triggered.")
            except Exception as e:
                st.error(f"Report generation request failed: {e}")

        # Show actions/audit
        if st.button("Show history", key=f"history_{case['review_id']}"):
            try:
                client = ui_api.api_client()
                r = client.get(f"/{case['review_id']}/actions")
                r.raise_for_status()
                st.json(r.json())
            except Exception as e:
                st.error(f"Failed to fetch history: {e}")


def _tag_badge(tag: str) -> str:
    color = TAG_PAL[hash(tag) % len(TAG_PAL)]
    return f"<span style='background:{color}; padding:2px 6px; border-radius:6px; margin-right:4px;'>{tag}</span>"
