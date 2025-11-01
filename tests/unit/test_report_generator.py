"""Unit tests for the report generator.

Mocks VectorStore, StructuredStore, TemplateEngine, and OllamaLLM to keep tests
deterministic and offline.
"""

from unittest.mock import MagicMock

import pytest

from i4g.reports.generator import ReportGenerator


class DummyRec:
    def __init__(self, case_id: str, text: str):
        self.case_id = case_id
        self.text = text

    def to_dict(self):
        return {"case_id": self.case_id, "text": self.text, "entities": {}}


@pytest.fixture
def mock_structured(tmp_path):
    """Mock StructuredStore with list_recent and get_by_id."""
    ms = MagicMock()
    ms.list_recent.return_value = [
        DummyRec("r1", "foo").to_dict(),
        DummyRec("r2", "bar").to_dict(),
    ]
    ms.get_by_id.return_value = DummyRec("r1", "foo")
    return ms


@pytest.fixture
def mock_vector(tmp_path):
    """Mock VectorStore with query_similar."""
    mv = MagicMock()
    # Return a list of dict-like metadata expected by generator._aggregate_structured
    mv.query_similar.return_value = [
        {
            "case_id": "r1",
            "text": "foo",
            "entities": {"people": ["Alice"], "wallet_addresses": ["0x1"]},
        },
        {
            "case_id": "r2",
            "text": "bar",
            "entities": {"people": ["Bob"], "wallet_addresses": ["0x2"]},
        },
    ]
    return mv


@pytest.fixture
def mock_templates(tmp_path):
    mt = MagicMock()
    mt.render.return_value = "Rendered content"
    return mt


@pytest.fixture
def mock_llm(monkeypatch):
    mm = MagicMock()
    mm.invoke.return_value = "LLM summary"
    monkeypatch.setattr("i4g.reports.generator.OllamaLLM", lambda model: mm)
    return mm


def test_generate_report_local_save(tmp_path, mock_structured, mock_vector, mock_templates, mock_llm):
    """Test the generate_report flow saves a file and returns expected keys."""
    rg = ReportGenerator(
        structured_store=mock_structured,
        vector_store=mock_vector,
        template_engine=mock_templates,
        llm_model="fake-model",
    )
    result = rg.generate_report(text_query="test query", template_name="base_template.md.j2", top_k=2)
    assert "report_path" in result
    assert "summary" in result
    assert result["aggregated_entities"]["people"]  # contains aggregated people list


def test_generate_report_handles_missing_template(tmp_path, mock_structured, mock_vector, mock_llm):
    """If the template is not found, generator falls back to auto-generated markdown."""
    # Use a TemplateEngine mock that raises FileNotFoundError on render
    mt = MagicMock()
    mt.render.side_effect = FileNotFoundError("not found")
    rg = ReportGenerator(
        structured_store=mock_structured,
        vector_store=mock_vector,
        template_engine=mt,
        llm_model="fake-model",
    )
    result = rg.generate_report(text_query="fallback test", template_name="nonexistent.j2")
    assert "report_path" in result
    assert "summary" in result
