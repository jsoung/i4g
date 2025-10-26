"""Report generator for i4g (M5.1).

This module builds a law-enforcement-ready case report by:
1. Retrieving related cases via vector search.
2. Aggregating structured evidence from the structured store.
3. Summarizing and drafting human-readable sections using an LLM (Ollama).
4. Rendering a Jinja2 template into Markdown.
5. Saving the report locally or (optionally) uploading to Google Docs.

The Google Docs upload is left as a stub in `gdoc_exporter.upload_to_gdocs`.
"""

from __future__ import annotations

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from i4g.store.structured import StructuredStore
from i4g.store.vector import VectorStore
from i4g.reports.template_engine import TemplateEngine
from i4g.reports.gdoc_exporter import export_to_gdoc
from langchain_ollama import OllamaLLM

DEFAULT_REPORTS_DIR = os.path.abspath(os.path.join(os.getcwd(), "reports"))


class ReportGenerator:
    """High-level report builder.

    Args:
        structured_store: Optional StructuredStore instance.
        vector_store: Optional VectorStore instance.
        template_engine: Optional TemplateEngine instance.
        llm_model: Ollama model name to use for summarization.
    """

    def __init__(
        self,
        structured_store: Optional[StructuredStore] = None,
        vector_store: Optional[VectorStore] = None,
        template_engine: Optional[TemplateEngine] = None,
        llm_model: str = "llama3.1",
    ) -> None:
        self.structured = structured_store or StructuredStore()
        self.vector = vector_store or VectorStore()
        self.templates = template_engine or TemplateEngine()
        self.reports_dir = DEFAULT_REPORTS_DIR
        os.makedirs(self.reports_dir, exist_ok=True)
        self.llm = OllamaLLM(model=llm_model)

    # ---- Retrieval helpers ----
    def _fetch_related_cases(self, case_id: Optional[str] = None, text_query: Optional[str] = None, top_k: int = 8) -> List[Dict[str, Any]]:
        """Fetch related cases using vector similarity or structured lookup.

        Priority:
        - If case_id provided, use the stored text to query the vector store.
        - Else if text_query provided, use it directly.
        - Else return recent cases from structured store.
        """
        if case_id:
            base = self.structured.get_by_id(case_id)
            if base and getattr(base, "text", None):
                query = base.text
            else:
                query = text_query or ""
        else:
            query = text_query or ""

        if query:
            try:
                results = self.vector.query_similar(query, top_k=top_k)
                return results
            except Exception:
                # Best-effort fallback: return recent structured records
                return [r.to_dict() for r in self.structured.list_recent(limit=top_k)]
        # No query: return recent records
        return [r.to_dict() for r in self.structured.list_recent(limit=top_k)]

    # ---- Aggregation / Summarization helpers ----
    def _aggregate_structured(self, related: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate entities across related cases into a summary structure."""
        agg = {
            "people": set(),
            "organizations": set(),
            "wallets": set(),
            "assets": set(),
            "contacts": set(),
            "locations": set(),
            "scam_indicators": set(),
        }
        for r in related:
            ents = r.get("entities") or {}
            for k, vals in ents.items():
                for v in vals:
                    if not v:
                        continue
                    key = k
                    if "wallet" in k:
                        agg["wallets"].add(v)
                    elif "crypto" in k or "asset" in k:
                        agg["assets"].add(v)
                    elif k == "people":
                        agg["people"].add(v)
                    elif k == "organizations":
                        agg["organizations"].add(v)
                    elif k == "contact_channels":
                        agg["contacts"].add(v)
                    elif k == "locations":
                        agg["locations"].add(v)
                    elif k == "scam_indicators":
                        agg["scam_indicators"].add(v)
        # Convert sets to sorted lists
        return {k: sorted(list(v)) for k, v in agg.items()}

    def _llm_summarize(self, related: List[Dict[str, Any]], prompt_extra: Optional[str] = None) -> str:
        """Ask the LLM to produce a human-readable summary of the evidence.

        This is intentionally thin — a project-specific prompt can improve results.
        """
        # Build a short context (concatenate texts, but keep length controlled)
        texts = []
        for r in related[:8]:
            t = r.get("text") or r.get("text", "")
            if t:
                texts.append(t if len(t) < 1000 else t[:1000] + " ...")
        context = "\n\n".join(texts)
        prompt = (
            "You are an assistant that summarizes evidence for law enforcement. "
            "Given the following case texts, produce a concise, factual summary emphasizing "
            "entities (people, wallets, organizations), timeline clues, and potential links.\n\n"
            f"{context}\n\n"
        )
        if prompt_extra:
            prompt += prompt_extra
        # Call LLM
        try:
            resp = self.llm.invoke(prompt)
            return str(resp)
        except Exception:
            # Fail gracefully: return a lightweight extracted summary
            return "Summary generation failed; please review raw evidence."

    # ---- Template / Render / Output ----
    def generate_report(
        self,
        case_id: Optional[str] = None,
        text_query: Optional[str] = None,
        template_name: str = "base_template.md.j2",
        top_k: int = 8,
        upload_to_gdocs_flag: bool = False,
    ) -> Dict[str, Any]:
        """Generate a report and save it to disk (and optionally upload to Google Docs).

        Args:
            case_id: Optional primary case id to anchor the search.
            text_query: Optional free-text query if case_id is not provided.
            template_name: Name of the Jinja2 template in templates/ directory.
            top_k: Number of related cases to retrieve.
            upload_to_gdocs_flag: If True, attempt to upload to Google Docs.
            gdrive_credentials: Optional credentials for Google API.

        Returns:
            A dictionary containing:
                - report_path: saved markdown path
                - gdoc_url: URL or id if uploaded (or None)
                - summary: LLM summary string
                - aggregated_entities: aggregated structured entities
        """
        related = self._fetch_related_cases(case_id=case_id, text_query=text_query, top_k=top_k)
        aggregated = self._aggregate_structured(related)
        summary = self._llm_summarize(related)

        # Context for the template
        context = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            "anchor_case_id": case_id,
            "query": text_query,
            "summary": summary,
            "related_cases": related,
            "entities": aggregated,
        }

        # Render
        try:
            rendered = self.templates.render(template_name, context)
        except FileNotFoundError:
            # Fallback: simple auto-generated markdown
            rendered = f"# i4g Report\n\nGenerated: {context['generated_at']}\n\n## Summary\n\n{summary}\n\n## Entities\n\n{json.dumps(aggregated, indent=2)}\n"

        # Export the report
        title = f"i4g Report {context['report_id']}"
        export_result = export_to_gdoc(
            title=title,
            content=rendered,
            offline=not upload_to_gdocs_flag
        )

        return {
            "report_path": export_result.get("local_path"),
            "gdoc_url": export_result.get("url"),
            "summary": summary,
            "aggregated_entities": aggregated,
        }
