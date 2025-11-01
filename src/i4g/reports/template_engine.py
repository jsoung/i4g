"""Jinja2-based template rendering for i4g reports.

Templates live in the top-level `templates/` directory by project design
(so they are editable without touching package code). This module provides
simple rendering utilities and a small stub for future template-learning.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

DEFAULT_TEMPLATES_DIR = os.path.abspath(os.path.join(os.getcwd(), "templates"))


class TemplateEngine:
    """Load and render Jinja2 templates from the `templates/` directory.

    Args:
        templates_dir: Directory where templates live (default: ./templates).
    """

    def __init__(self, templates_dir: Optional[str] = None) -> None:
        self.templates_dir = templates_dir or DEFAULT_TEMPLATES_DIR
        loader = FileSystemLoader(self.templates_dir)
        self.env = Environment(
            loader=loader,
            autoescape=select_autoescape(enabled_extensions=("html", "xml", "md")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def list_templates(self) -> List[str]:
        """Return a list of template names available in the templates directory."""
        try:
            return list(self.env.list_templates())
        except Exception:
            return []

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a named template with the provided context.

        Args:
            template_name: Template file name (e.g., "fbi_template.md.j2").
            context: Mapping of template variables.

        Returns:
            Rendered string (typically Markdown).

        Raises:
            FileNotFoundError: If the template does not exist.
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound as e:
            raise FileNotFoundError(f"Template not found: {template_name}") from e
        return template.render(**context)

    # --- Stub: template learning (future work) ---
    def learn_templates_from_examples(self, example_report_paths: List[str]) -> None:
        """Stub: Analyze example reports and generate/update templates.

        This is intentionally a stub. Future work will:
        - Parse example reports (markdown/docx/gdoc exports)
        - Cluster similar report structures
        - Propose or generate Jinja2 templates for analysts to review

        Args:
            example_report_paths: Paths to historical reports to learn from.
        """
        # Placeholder — no-op for now.
        return None
