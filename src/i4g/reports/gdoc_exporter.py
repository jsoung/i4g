"""Google Docs Exporter for i4g Reports (GCP-aware authentication).

Supports:
1. Local file export (offline fallback).
2. Google Docs export (authenticated via ADC or service account).
"""

from __future__ import annotations
import os
import datetime
from pathlib import Path
from typing import Optional, Dict

from google.auth import default as google_auth_default
from google.oauth2 import service_account
from googleapiclient.discovery import build


def _save_local_fallback(content: str, title: str) -> str:
    """Fallback: save report locally if offline or credentials missing."""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    filename = f"{title.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path = reports_dir / filename
    path.write_text(content, encoding="utf-8")
    return str(path.resolve())


def _get_gcp_credentials():
    """Retrieve GCP credentials using best available method.

    Priority:
        1. Application Default Credentials (ADC) via `gcloud auth application-default login`
           or running inside GCP environment.
        2. GOOGLE_APPLICATION_CREDENTIALS (Service Account JSON).
        3. Raise a clear error if neither is available.

    Returns:
        google.auth.credentials.Credentials
    """
    try:
        creds, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/documents"])
        return creds
    except Exception:
        service_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if service_file and os.path.exists(service_file):
            creds = service_account.Credentials.from_service_account_file(
                service_file,
                scopes=["https://www.googleapis.com/auth/documents"],
            )
            return creds
        raise RuntimeError(
            "No valid GCP credentials found. Please run:\n"
            "  gcloud auth application-default login\n"
            "or set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON file."
        )


def export_to_gdoc(
    title: str,
    content: str,
    offline: bool = True,
) -> Dict[str, Optional[str]]:
    """Export a rendered report to Google Docs or save locally if offline.

    Args:
        title: The report title.
        content: The report content (Markdown or text).
        offline: If True, saves locally instead of uploading.

    Returns:
        A dictionary with:
            - "url": Google Docs URL if uploaded.
            - "local_path": path to saved file if offline.
            - "mode": "gdoc" or "offline".
    """
    if offline:
        local_path = _save_local_fallback(content, title)
        return {"url": None, "local_path": local_path, "mode": "offline"}

    creds = _get_gcp_credentials()
    service = build("docs", "v1", credentials=creds)
    doc = service.documents().create(body={"title": title}).execute()
    doc_id = doc.get("documentId")

    requests = [{"insertText": {"location": {"index": 1}, "text": content}}]
    service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    url = f"https://docs.google.com/document/d/{doc_id}/edit"
    return {"url": url, "local_path": None, "mode": "gdoc"}