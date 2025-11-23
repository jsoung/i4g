"""Unit tests for shared ingestion payload helpers."""

from __future__ import annotations

from i4g.services.ingest_payloads import prepare_ingest_payload


def test_prepare_payload_prefers_record_text_and_entities():
    record = {
        "case_id": "case-1",
        "text": "Primary text",
        "entities": {"email": [{"value": "test@example.com"}]},
        "fraud_type": "advance_fee",
        "fraud_confidence": 0.9,
        "metadata": {"classification": "should_not_override"},
    }

    payload, diagnostics = prepare_ingest_payload(record)

    assert payload["case_id"] == "case-1"
    assert payload["text"] == "Primary text"
    assert payload["entities"] == {"email": [{"value": "test@example.com"}]}
    assert payload["fraud_type"] == "advance_fee"
    assert payload["fraud_confidence"] == 0.9
    assert diagnostics["classification"] == "advance_fee"
    assert diagnostics["text_source"] == "record.text"
    assert diagnostics["entities_source"] == "record.entities"


def test_prepare_payload_derives_text_from_summary_and_metadata():
    record = {
        "intake_id": "intake-42",
        "summary": "Short summary",
        "details": "Detailed narrative",
        "metadata": {
            "classification": "crypto_scam",
            "classification_confidence": "0.75",
            "entities": {"wallet": ["0x123"]},
        },
    }

    payload, diagnostics = prepare_ingest_payload(record)

    assert payload["case_id"] == "intake-42"
    assert payload["text"] == "Short summary\n\nDetailed narrative"
    assert payload["fraud_type"] == "crypto_scam"
    assert payload["fraud_confidence"] == 0.75
    assert payload["entities"] == {"wallet": ["0x123"]}
    assert diagnostics["classification"] == "crypto_scam"
    assert diagnostics["text_source"] == "derived"
    assert diagnostics["entities_source"] == "metadata.entities"


def test_prepare_payload_handles_missing_fields_gracefully():
    record = {}

    payload, diagnostics = prepare_ingest_payload(record)

    assert payload["case_id"] is None
    assert payload["text"] == ""
    assert payload["fraud_type"] == "unclassified"
    assert payload["fraud_confidence"] == 0.0
    assert payload["entities"] == {}
    assert diagnostics["text_source"] == "none"
    assert diagnostics["entities_source"] == "none"
