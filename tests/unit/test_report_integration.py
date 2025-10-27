"""Integration-style unit tests for i4g.reports.generator.ReportGenerator."""

import pytest
from unittest import mock

from i4g.reports.generator import ReportGenerator


pytestmark = pytest.mark.integration


@pytest.fixture
def mock_dependencies():
    """Provide mocked dependencies for ReportGenerator."""
    with (
        mock.patch("i4g.reports.generator.StructuredStore") as MockStructured,
        mock.patch("i4g.reports.generator.VectorStore") as MockVector,
        mock.patch("i4g.reports.generator.TemplateEngine") as MockTemplate,
        mock.patch("i4g.reports.generator.OllamaLLM") as MockLLM,
        mock.patch("i4g.reports.generator.export_to_gdoc") as mock_export,
    ):
        # Configure mock instances
        mock_structured_instance = MockStructured.return_value
        mock_vector_instance = MockVector.return_value
        mock_template_instance = MockTemplate.return_value
        mock_llm_instance = MockLLM.return_value

        # Mock method return values
        mock_vector_instance.query_similar.return_value = [{"text": "related case 1"}]
        mock_llm_instance.invoke.return_value = "This is an LLM summary."
        mock_template_instance.render.return_value = "# Rendered Report Content"
        mock_export.return_value = {"local_path": "/path/to/report.md", "url": "http://docs.google.com/id/123"}

        yield {
            "structured": mock_structured_instance,
            "vector": mock_vector_instance,
            "template": mock_template_instance,
            "llm": mock_llm_instance,
            "export": mock_export,
        }


def test_generate_report_integration(mock_dependencies):
    """Verify the end-to-end flow of ReportGenerator.generate_report."""
    # 1. Initialize the generator (dependencies are auto-mocked by the fixture)
    generator = ReportGenerator()

    # 2. Run the report generation for local export
    result_offline = generator.generate_report(
        text_query="test query",
        upload_to_gdocs_flag=False
    )

    # 3. Assertions for offline mode
    mock_dependencies["vector"].query_similar.assert_called_with("test query", top_k=8)
    mock_dependencies["llm"].invoke.assert_called_once()
    mock_dependencies["template"].render.assert_called_with("base_template.md.j2", mock.ANY)
    mock_dependencies["export"].assert_called_once_with(
        title=mock.ANY,
        content="# Rendered Report Content",
        offline=True
    )
    assert result_offline["report_path"] == "/path/to/report.md"
    assert result_offline["summary"] == "This is an LLM summary."

    # 4. Reset mocks and run for online export
    mock_dependencies["export"].reset_mock()

    result_online = generator.generate_report(
        text_query="another query",
        upload_to_gdocs_flag=True
    )

    # 5. Assertions for online mode
    mock_dependencies["export"].assert_called_once_with(
        title=mock.ANY,
        content="# Rendered Report Content",
        offline=False
    )
    assert result_online["gdoc_url"] == "http://docs.google.com/id/123"
