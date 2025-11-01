"""Unit tests for the template engine."""

import os
from pathlib import Path

import pytest

from i4g.reports.template_engine import TemplateEngine


def test_render_simple_template(tmp_path):
    """Create a temporary template and render it with context."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    template_file = templates_dir / "simple.md.j2"
    template_file.write_text("Hello {{ name }}\nValue: {{ value }}\n")

    engine = TemplateEngine(templates_dir=str(templates_dir))
    rendered = engine.render("simple.md.j2", {"name": "Alice", "value": 42})
    assert "Hello Alice" in rendered
    assert "Value: 42" in rendered


def test_list_templates(tmp_path):
    """Ensure listing returns created templates."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "a.j2").write_text("A")
    (templates_dir / "b.j2").write_text("B")

    engine = TemplateEngine(templates_dir=str(templates_dir))
    names = engine.list_templates()
    assert "a.j2" in names and "b.j2" in names


def test_missing_template_raises(tmp_path):
    """Missing templates produce a FileNotFoundError from render."""
    engine = TemplateEngine(templates_dir=str(tmp_path / "empty"))
    with pytest.raises(FileNotFoundError):
        engine.render("does-not-exist.j2", {})
