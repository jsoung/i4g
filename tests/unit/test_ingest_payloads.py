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
    assert payload["metadata"]["classification"] == "should_not_override"
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


def test_prepare_payload_adds_dataset_and_category_metadata():
    record = {
        "category": "romance",
        "metadata": {
            "dataset": "meta-dataset",
            "indicator_ids": [
                {"indicator_id": "indicator-1"},
                {"value": "indicator-2"},
            ],
            "tags": ["romance", "crypto"],
            "summary": "visa office",
            "channel": "chat",
        },
    }

    payload, _ = prepare_ingest_payload(record, default_dataset="fallback-dataset")

    assert payload["dataset"] == "meta-dataset"
    assert payload["categories"] == ["romance"]
    assert payload["indicator_ids"] == ["indicator-1", "indicator-2"]
    assert payload["summary"] == "visa office"
    assert payload["tags"] == ["romance", "crypto"]
    assert payload["channel"] == "chat"


def test_prepare_payload_uses_default_dataset_when_missing():
    record = {
        "metadata": {},
    }

    payload, _ = prepare_ingest_payload(record, default_dataset="retrieval_poc")

    assert payload["dataset"] == "retrieval_poc"


def test_prepare_payload_copies_document_fields():
    record = {
        "case_id": "case-9",
        "text": "body",
        "document_id": "doc-1",
        "document_title": "title",
        "source_url": "https://example.com",
        "tags": ["tag1", "tag2"],
        "structured_fields": {"payment_method": "crypto"},
        "metadata": {"risk_level": "high", "language": "en"},
        "ground_truth_label": "template-1",
    }

    payload, _ = prepare_ingest_payload(record)

    assert payload["document_id"] == "doc-1"
    assert payload["document_title"] == "title"
    assert payload["source_url"] == "https://example.com"
    assert payload["tags"] == ["tag1", "tag2"]
    assert payload["structured_fields"] == {"payment_method": "crypto"}
    assert payload["risk_level"] == "high"
    assert payload["language"] == "en"
    assert payload["ground_truth_label"] == "template-1"


def test_prepare_payload_enriches_network_entities_without_duplicates():
    record = {
        "case_id": "case-network",
        "text": "Browser + network indicators",
        "entities": {"ip_address": [{"value": "198.51.100.10"}]},
        "structured_fields": {
            "network": {
                "browser_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0)",
                "ip_address": ["203.0.113.25", {"value": "198.51.100.10"}],
            },
            "asn": 64512,
        },
        "metadata": {
            "network": {
                "client_ip": "203.0.113.25",
                "asn_number": "AS13335",
            }
        },
    }

    payload, diagnostics = prepare_ingest_payload(record)

    entities = payload["entities"]
    assert entities["ip_address"] == [
        {"value": "198.51.100.10"},
        {"value": "203.0.113.25"},
    ]
    assert entities["browser_agent"] == [{"value": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0)"}]
    assert {entry["value"] for entry in entities["asn"]} == {"64512", "AS13335"}
    assert diagnostics["entities_source"].endswith("+network")
