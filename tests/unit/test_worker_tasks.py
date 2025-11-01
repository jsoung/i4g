"""
Unit tests for i4g.worker.tasks.
"""

from unittest.mock import MagicMock, patch

from i4g.worker.tasks import generate_report_for_case


@patch("i4g.worker.tasks.ReviewStore")
@patch("i4g.worker.tasks.ReportGenerator")
def test_generate_report_success(mock_report_generator_cls, mock_store_cls):
    """Ensure successful report creation and export are logged correctly."""
    mock_store = MagicMock()
    mock_store.get_review.return_value = {
        "review_id": "rev-1",
        "case_id": "CASE1",
        "status": "accepted",
    }
    mock_store_cls.return_value = mock_store

    mock_generator_instance = MagicMock()
    mock_generator_instance.generate_report.return_value = {"gdoc_url": "doc-123"}
    mock_report_generator_cls.return_value = mock_generator_instance

    doc_id = generate_report_for_case("rev-1")

    assert doc_id == "doc-123"
    mock_store.get_review.assert_called_once_with("rev-1")
    mock_report_generator_cls.assert_called_once()
    mock_generator_instance.generate_report.assert_called_once_with(case_id="CASE1", upload_to_gdocs_flag=True)
    mock_store.log_action.assert_called_once_with(
        "rev-1",
        actor="worker",
        action="report_generated",
        payload={"gdoc_id": "doc-123"},
    )


@patch("i4g.worker.tasks.ReviewStore")
def test_generate_report_skips_unaccepted(mock_store_cls):
    """Should skip when review status is not 'accepted'."""
    mock_store = MagicMock()
    mock_store.get_review.return_value = {"review_id": "rev-2", "status": "queued"}
    mock_store_cls.return_value = mock_store

    result = generate_report_for_case("rev-2")
    assert "not_accepted" in result


@patch("i4g.worker.tasks.ReviewStore")
def test_generate_report_handles_missing_case(mock_store_cls):
    """Should return an error when review not found."""
    mock_store = MagicMock()
    mock_store.get_review.return_value = None
    mock_store_cls.return_value = mock_store

    result = generate_report_for_case("rev-404")
    assert "review_not_found" in result


@patch("i4g.worker.tasks.ReviewStore")
@patch("i4g.worker.tasks.ReportGenerator")
def test_generate_report_success(mock_report_generator_cls, mock_store_cls):
    """Ensure successful report creation and export are logged correctly."""
    mock_store = MagicMock()
    mock_store.get_review.return_value = {
        "review_id": "rev-1",
        "case_id": "CASE1",
        "status": "accepted",
    }
    mock_store_cls.return_value = mock_store

    mock_generator_instance = MagicMock()
    mock_generator_instance.generate_report.return_value = {"report_path": "/path/to/report.docx"}
    mock_report_generator_cls.return_value = mock_generator_instance

    doc_id = generate_report_for_case("rev-1")

    assert doc_id == "/path/to/report.docx"
    mock_store.get_review.assert_called_once_with("rev-1")
    mock_report_generator_cls.assert_called_once()
    mock_generator_instance.generate_report.assert_called_once_with(case_id="CASE1")
    mock_store.log_action.assert_called_once_with(
        "rev-1",
        actor="worker",
        action="report_generated",
        payload={"report_path": "/path/to/report.docx"},
    )
