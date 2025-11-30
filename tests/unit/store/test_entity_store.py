"""Unit tests for the SQL-backed EntityStore helper."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from i4g.store import sql as sql_schema
from i4g.store.entity_store import EntityStore


def _session_factory() -> sessionmaker:
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    sql_schema.METADATA.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_case_with_indicator(
    session,
    *,
    case_id: str,
    dataset: str,
    indicator_number: str,
    loss_amount: float | None = None,
) -> None:
    case_metadata: Dict[str, Any] = {"dataset": dataset}
    if loss_amount is not None:
        case_metadata["loss_amount"] = loss_amount

    session.execute(
        sql_schema.cases.insert(),
        {
            "case_id": case_id,
            "dataset": dataset,
            "source_type": "ocr",
            "classification": "romance",
            "confidence": 0.9,
            "detected_at": datetime.utcnow(),
            "reported_at": datetime.utcnow(),
            "raw_text_sha256": f"sha-{case_id}",
            "status": "open",
            "metadata": case_metadata,
        },
    )
    session.execute(
        sql_schema.indicators.insert(),
        {
            "indicator_id": f"ind-{case_id}",
            "case_id": case_id,
            "category": "bank_account",
            "type": "account_number",
            "number": indicator_number,
            "dataset": dataset,
            "metadata": {"dataset": dataset},
        },
    )
    session.commit()


def test_search_cases_by_indicator_filters_dataset_and_loss_bucket():
    factory = _session_factory()
    store = EntityStore(session_factory=factory)
    with factory() as session:
        _seed_case_with_indicator(
            session,
            case_id="case-a",
            dataset="retrieval_poc_dev",
            indicator_number="021000021-123456789",
            loss_amount=25000,
        )

    results = store.search_cases_by_indicator(
        indicator_type="bank_account",
        value="021000021",
        match_mode="prefix",
        datasets=["retrieval_poc_dev"],
        loss_buckets=["10k-50k"],
        limit=10,
    )

    assert len(results) == 1
    assert results[0]["case_id"] == "case-a"
    assert results[0]["loss_amount"] == 25000


def test_search_cases_by_indicator_honors_mismatch_filters():
    factory = _session_factory()
    store = EntityStore(session_factory=factory)
    with factory() as session:
        _seed_case_with_indicator(
            session,
            case_id="case-b",
            dataset="account_list",
            indicator_number="999-222-111",
            loss_amount=5000,
        )

    # Dataset mismatch
    assert (
        store.search_cases_by_indicator(
            indicator_type="bank_account",
            value="999",
            match_mode="prefix",
            datasets=["retrieval_poc_dev"],
            loss_buckets=None,
            limit=5,
        )
        == []
    )

    # Loss bucket mismatch
    assert (
        store.search_cases_by_indicator(
            indicator_type="bank_account",
            value="999",
            match_mode="contains",
            datasets=["account_list"],
            loss_buckets=[">50k"],
            limit=5,
        )
        == []
    )
