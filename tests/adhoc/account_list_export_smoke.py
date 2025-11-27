"""Manual smoke test for the account list exporter pipeline.

This script fabricates a small set of source documents and indicators, then
runs :class:`AccountListService` with stub retriever/extractor components so we
can verify artifact export paths without relying on the full LLM workflow.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from i4g.services.account_list.exporters import AccountListExporter
from i4g.services.account_list.models import AccountListRequest, FinancialIndicator, SourceDocument
from i4g.services.account_list.queries import IndicatorQuery
from i4g.services.account_list.service import AccountListService

DEFAULT_FORMATS = ["csv", "json", "xlsx", "pdf"]


@dataclass
class _StaticRetriever:
    """Return the same synthetic documents for every query."""

    documents: Sequence[SourceDocument]

    def fetch_documents(
        self,
        *,
        indicator_query: IndicatorQuery,
        top_k: int,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> List[SourceDocument]:
        del indicator_query, start_time, end_time
        return list(self.documents[:top_k])


class _StaticExtractor:
    """Generate deterministic indicators for the provided documents."""

    def extract_indicators(
        self,
        *,
        query: IndicatorQuery,
        documents: Iterable[SourceDocument],
    ) -> List[FinancialIndicator]:
        indicators: List[FinancialIndicator] = []
        for idx, doc in enumerate(documents, start=1):
            indicators.append(
                FinancialIndicator(
                    category=query.slug,
                    type=query.indicator_type,
                    item=f"{query.slug.title()} Indicator #{idx}",
                    number=f"{doc.case_id}-ACCT-{idx:03d}",
                    source_case_id=doc.case_id,
                    metadata={
                        "source_title": doc.title,
                        "confidence": 0.95 - (idx * 0.01),
                    },
                )
            )
        return indicators


def _build_documents(count: int) -> List[SourceDocument]:
    """Create synthetic documents for the smoke test."""

    now = datetime.now(tz=timezone.utc)
    documents: List[SourceDocument] = []
    for idx in range(count):
        documents.append(
            SourceDocument(
                case_id=f"SMOKE-{idx + 1:03d}",
                content=f"Synthetic transaction narrative #{idx + 1}.",
                dataset="account_smoke",
                title=f"Mock Account Case {idx + 1}",
                classification="account_smoke",
                created_at=now - timedelta(days=idx),
                score=0.95 - (idx * 0.02),
                excerpt="Sample excerpt used to verify artifact exports.",
            )
        )
    return documents


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export mock account list artifacts for smoke testing.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/account_list_smoke"),
        help="Directory where artifact files should be written.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=DEFAULT_FORMATS,
        help="Artifact formats to generate (csv, json, xlsx, pdf).",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=["bank", "crypto"],
        help="Indicator categories passed to the service.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of indicators requested per category.",
    )
    parser.add_argument(
        "--documents",
        type=int,
        default=3,
        help="Synthetic documents to generate for the retriever stub.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the account list export smoke CLI."""

    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    documents = _build_documents(args.documents)
    retriever = _StaticRetriever(documents=documents)
    extractor = _StaticExtractor()
    exporter = AccountListExporter(base_dir=args.output_dir)

    service = AccountListService(
        retriever=retriever,
        extractor=extractor,
        exporter=exporter,
    )

    window_end = datetime.now(tz=timezone.utc)
    request = AccountListRequest(
        start_time=window_end - timedelta(days=14),
        end_time=window_end,
        categories=args.categories,
        top_k=args.top_k,
        include_sources=True,
        output_formats=args.formats,
    )

    result = service.run(request)

    print("Account list smoke test completed")
    print(f"Request ID: {result.request_id}")
    print(f"Indicators returned: {len(result.indicators)}")
    artifacts = result.artifacts or {}
    if not artifacts:
        print("No artifacts generated; check exporter settings.")
    else:
        print("Artifacts:")
        for fmt, path in artifacts.items():
            print(f"  - {fmt}: {path}")


if __name__ == "__main__":
    main()
