"""Tests for the local intake job runner implementation."""

from __future__ import annotations

from i4g.services.intake_job_runner import LocalPipelineIntakeJobRunner


class DummyPipeline:
    def __init__(self, *, enable_vector: bool = True) -> None:
        self.last_payload = None
        self.enable_vector = enable_vector

    def ingest_classified_case(self, payload):
        self.last_payload = payload
        return payload.get("case_id") or "generated-case-id"


def test_local_runner_normalises_payload(monkeypatch):
    pipeline = DummyPipeline()

    runner = LocalPipelineIntakeJobRunner(pipeline_factory=lambda **_: pipeline)

    intake = {
        "intake_id": "intake-007",
        "summary": "Victim approached on social media",
        "details": "Eventually convinced to transfer crypto funds.",
        "metadata": {
            "classification": "romance_scam",
            "classification_confidence": "0.65",
            "entities": {"platform": ["instagram"]},
        },
    }

    result = runner.run(intake)

    assert pipeline.last_payload is not None
    assert pipeline.last_payload["text"].startswith("Victim approached")
    assert pipeline.last_payload["fraud_type"] == "romance_scam"
    assert pipeline.last_payload["entities"] == {"platform": ["instagram"]}
    assert result.case_id == "intake-007"
    assert result.metadata["classification"] == "romance_scam"
    assert result.metadata["confidence"] == 0.65
    assert result.metadata["text_source"] == "derived"
    assert result.metadata["runner"] == "local_pipeline"
    assert pipeline.enable_vector is True


def test_local_runner_reads_env_for_vector(monkeypatch):
    monkeypatch.setenv("I4G_INGEST__ENABLE_VECTOR", "false")
    created = {}

    def factory(**kwargs):
        created["kwargs"] = kwargs
        return DummyPipeline(enable_vector=kwargs.get("enable_vector", True))

    runner = LocalPipelineIntakeJobRunner(pipeline_factory=factory)
    runner.run({"summary": "test", "details": "payload"})

    assert created["kwargs"]["enable_vector"] is False
