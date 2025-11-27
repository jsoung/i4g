"""High-level orchestration for account list extraction."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

from i4g.settings import Settings, get_settings

from .exporters import AccountListExporter
from .llm_extractor import AccountEntityExtractor
from .models import AccountListRequest, AccountListResult, FinancialIndicator, SourceDocument
from .queries import IndicatorQuery, get_indicator_query, list_indicator_queries
from .retriever import FinancialEntityRetriever

LOGGER = logging.getLogger(__name__)


class AccountListService:
    """Coordinates retrieval, extraction, and aggregation of indicators."""

    def __init__(
        self,
        *,
        retriever: FinancialEntityRetriever | None = None,
        extractor: AccountEntityExtractor | None = None,
        exporter: AccountListExporter | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or FinancialEntityRetriever()
        self.extractor = extractor or AccountEntityExtractor(settings=self.settings)
        self.exporter = exporter or AccountListExporter(settings=self.settings)

    def run(self, request: AccountListRequest) -> AccountListResult:
        """Execute an extraction run and return normalized indicators."""

        request_id = f"account-run-{uuid4().hex[:8]}"
        generated_at = datetime.now(tz=timezone.utc)
        categories = request.categories or [query.slug for query in list_indicator_queries()]
        indicators: List[FinancialIndicator] = []
        source_lookup: Dict[str, SourceDocument] = {}
        warnings: List[str] = []

        for category in categories:
            try:
                query = get_indicator_query(category)
            except KeyError:
                warnings.append(f"Unknown indicator category skipped: {category}")
                continue
            documents = self.retriever.fetch_documents(
                indicator_query=query,
                top_k=request.top_k,
                start_time=request.start_time,
                end_time=request.end_time,
            )
            if not documents:
                warnings.append(f"No documents found for category {query.slug}")
                continue
            for doc in documents:
                source_lookup.setdefault(doc.case_id, doc)
            extracted = self.extractor.extract_indicators(query=query, documents=documents)
            if not extracted:
                warnings.append(f"No indicators extracted for category {query.slug}")
            indicators.extend(extracted)

        deduped = self._deduplicate(indicators)
        sources = list(source_lookup.values()) if request.include_sources else []
        metadata = {
            "category_count": len(categories),
            "indicator_count": len(deduped),
            "requested_top_k": request.top_k,
        }
        result = AccountListResult(
            request_id=request_id,
            generated_at=generated_at,
            indicators=deduped,
            sources=sources,
            warnings=warnings,
            metadata=metadata,
        )

        artifact_formats = request.output_formats or self.settings.account_list.default_formats or []
        if artifact_formats:
            try:
                artifacts = self.exporter.export(result, artifact_formats)
            except Exception:  # pragma: no cover - filesystem failures
                LOGGER.exception("Failed to export account list artifacts for %s", request_id)
                warnings.append("Artifact generation failed; check server logs")
                result = result.model_copy(update={"warnings": list(warnings)})
            else:
                if artifacts:
                    result = result.model_copy(update={"artifacts": artifacts})
        return result

    @staticmethod
    def _deduplicate(indicators: List[FinancialIndicator]) -> List[FinancialIndicator]:
        seen: set[tuple[str, str, str]] = set()
        result: List[FinancialIndicator] = []
        for indicator in indicators:
            key = (indicator.category.lower(), indicator.item.lower(), indicator.number.lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(indicator)
        return result
