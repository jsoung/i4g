"""Unit tests for i4g.reports.gdoc_exporter."""

import io
import os
import tempfile
from unittest import mock
from pathlib import Path

import pytest

from i4g.reports import gdoc_exporter


def test_save_local_fallback_creates_file(tmp_path):
    """Ensure the fallback save function creates a text file with content."""
    title = "Sample Report"
    content = "This is a test report."
    result_path = gdoc_exporter._save_local_fallback(content, title)

    assert os.path.exists(result_path)
    with open(result_path, "r", encoding="utf-8") as f:
        data = f.read()
    assert "This is a test report." in data
    assert result_path.endswith(".txt")


@mock.patch("i4g.reports.gdoc_exporter._save_local_fallback")
def test_export_to_gdoc_offline_calls_fallback(mock_fallback):
    """When offline=True, should call fallback save and return offline mode."""
    mock_fallback.return_value = "/tmp/dummy_report.txt"
    result = gdoc_exporter.export_to_gdoc("Offline Test", "content", offline=True)

    mock_fallback.assert_called_once()
    assert result["mode"] == "offline"
    assert "dummy_report.txt" in result["local_path"]
    assert result["url"] is None


@mock.patch("i4g.reports.gdoc_exporter.google_auth_default")
@mock.patch("i4g.reports.gdoc_exporter.service_account")
def test_get_gcp_credentials_prefers_adc(mock_service_account, mock_google_auth_default):
    """Test that ADC credentials are used if available."""
    mock_creds = mock.MagicMock()
    mock_google_auth_default.return_value = (mock_creds, "project")
    creds = gdoc_exporter._get_gcp_credentials()

    assert creds == mock_creds
    mock_google_auth_default.assert_called_once()
    mock_service_account.Credentials.from_service_account_file.assert_not_called()


@mock.patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake_service.json"})
@mock.patch("os.path.exists", return_value=True)
@mock.patch("i4g.reports.gdoc_exporter.google_auth_default", side_effect=Exception("ADC unavailable"))
@mock.patch("i4g.reports.gdoc_exporter.service_account.Credentials.from_service_account_file")
def test_get_gcp_credentials_fallback_to_service_account(mock_from_sa, *_):
    """If ADC fails, falls back to service account file."""
    mock_creds = mock.MagicMock()
    mock_from_sa.return_value = mock_creds

    creds = gdoc_exporter._get_gcp_credentials()
    assert creds == mock_creds
    mock_from_sa.assert_called_once_with(
        "/tmp/fake_service.json",
        scopes=["https://www.googleapis.com/auth/documents"],
    )


@mock.patch("i4g.reports.gdoc_exporter.build")
@mock.patch("i4g.reports.gdoc_exporter._get_gcp_credentials")
def test_export_to_gdoc_online_creates_doc(mock_get_creds, mock_build):
    """Simulate Google Docs API creation and batch update."""
    mock_service = mock.Mock()
    mock_docs = mock.Mock()
    mock_docs.create.return_value.execute.return_value = {"documentId": "12345"}
    mock_service.documents.return_value = mock_docs
    mock_build.return_value = mock_service

    result = gdoc_exporter.export_to_gdoc("My Report", "This is content.", offline=False)

    mock_build.assert_called_once_with("docs", "v1", credentials=mock_get_creds())
    assert "12345" in result["url"]
    assert result["mode"] == "gdoc"
