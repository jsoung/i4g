"""Export utilities for i4g reports.

This module contains a lightweight local-export helper and a stubbed
Google Docs uploader (needs GCP credentials and OAuth setup).
"""

from __future__ import annotations

import os
from typing import Optional
from pathlib import Path


def save_markdown_to_file(markdown_text: str, out_path: str) -> str:
    """Save markdown content to a given file path.

    Args:
        markdown_text: Rendered markdown text.
        out_path: Destination file path.

    Returns:
        The path to the saved file (absolute).
    """
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markdown_text, encoding="utf-8")
    return str(p.resolve())


def upload_to_gdocs(markdown_text: str, title: str, gdrive_credentials: Optional[dict] = None) -> str:
    """Upload a rendered Markdown report to Google Docs.

    This is a stub: implement your preferred upload workflow here. Options:
    - Convert Markdown to HTML and call Google Docs API to create a document.
    - Use Google Drive API to upload a .docx file generated from Markdown (python-docx),
      then convert by Drive API to Google Docs format.
    - Use a pre-existing GCP service account + OAuth flow for an interactive upload.

    Args:
        markdown_text: The report content in Markdown.
        title: Desired Google Doc title.
        gdrive_credentials: Optional credentials/config (placeholder).

    Returns:
        The Google Docs URL (string) or document ID.

    Raises:
        NotImplementedError: Since this function is intentionally a stub.
    """
    # Raise with instructions so developers know how to continue.
    raise NotImplementedError(
        "Google Docs upload is not implemented. "
        "Provide gdrive_credentials and implement upload using Google Drive/Docs APIs. "
        "Suggested approach:\n"
        "1. Convert Markdown to HTML (or .docx).\n"
        "2. Use Google Drive API to upload the file.\n"
        "3. (Optional) Convert uploaded file to Google Docs MIME type.\n"
    )
