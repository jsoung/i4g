"""Dual extraction baseline schema."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20251129_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UUID_TYPE = sa.String(length=64)
TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    """Create tables supporting the dual-write ingestion pipeline."""

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", UUID_TYPE, primary_key=True),
        sa.Column("dataset", sa.Text(), nullable=False),
        sa.Column("source_bundle", sa.Text(), nullable=True),
        sa.Column("started_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", TIMESTAMP, nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indicator_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("firestore_writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vertex_writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sql_writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vector_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_ingestion_runs_started_at", "ingestion_runs", ["started_at"], unique=False)
    op.create_index("idx_ingestion_runs_status", "ingestion_runs", ["status"], unique=False)

    op.create_table(
        "cases",
        sa.Column("case_id", sa.Text(), primary_key=True),
        sa.Column("ingestion_run_id", UUID_TYPE, sa.ForeignKey("ingestion_runs.run_id", ondelete="SET NULL"), nullable=True),
        sa.Column("dataset", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("classification", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("detected_at", TIMESTAMP, nullable=True),
        sa.Column("reported_at", TIMESTAMP, nullable=True),
        sa.Column("raw_text_sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("dataset", "raw_text_sha256", name="uq_cases_dataset_rawsha"),
    )
    op.create_index("idx_cases_dataset_reported_at", "cases", ["dataset", "reported_at"], unique=False)
    op.create_index("idx_cases_classification", "cases", ["classification"], unique=False)
    op.create_index("idx_cases_status", "cases", ["status"], unique=False)

    op.create_table(
        "source_documents",
        sa.Column("document_id", UUID_TYPE, primary_key=True),
        sa.Column("case_id", sa.Text(), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_sha256", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("score", sa.Numeric(6, 3), nullable=True),
        sa.Column("captured_at", TIMESTAMP, nullable=True),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_documents_case", "source_documents", ["case_id", "captured_at"], unique=False)

    op.create_table(
        "entities",
        sa.Column("entity_id", UUID_TYPE, primary_key=True),
        sa.Column("case_id", sa.Text(), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("canonical_value", sa.Text(), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("first_seen_at", TIMESTAMP, nullable=True),
        sa.Column("last_seen_at", TIMESTAMP, nullable=True),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("case_id", "entity_type", "canonical_value", name="uq_entities_case_type_value"),
    )
    op.create_index("idx_entities_type_value", "entities", ["entity_type", "canonical_value"], unique=False)

    op.create_table(
        "entity_mentions",
        sa.Column("entity_id", UUID_TYPE, sa.ForeignKey("entities.entity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID_TYPE, sa.ForeignKey("source_documents.document_id", ondelete="CASCADE"), nullable=False),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("sentence", sa.Text(), nullable=True),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("entity_id", "document_id", "span_start", name="pk_entity_mentions"),
    )
    op.create_index("idx_entity_mentions_document", "entity_mentions", ["document_id"], unique=False)

    op.create_table(
        "indicators",
        sa.Column("indicator_id", UUID_TYPE, primary_key=True),
        sa.Column("case_id", sa.Text(), sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("item", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("first_seen_at", TIMESTAMP, nullable=True),
        sa.Column("last_seen_at", TIMESTAMP, nullable=True),
        sa.Column("dataset", sa.Text(), nullable=False),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("dataset", "category", "number", name="uq_indicators_dataset_category_number"),
    )
    op.create_index("idx_indicators_category_number", "indicators", ["category", "number"], unique=False)
    op.create_index("idx_indicators_case_id", "indicators", ["case_id"], unique=False)
    op.create_index("idx_indicators_last_seen_at", "indicators", ["last_seen_at"], unique=False)

    op.create_table(
        "indicator_sources",
        sa.Column("indicator_id", UUID_TYPE, sa.ForeignKey("indicators.indicator_id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID_TYPE, sa.ForeignKey("source_documents.document_id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", UUID_TYPE, sa.ForeignKey("entities.entity_id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("metadata", JSON_TYPE, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("indicator_id", "document_id", name="pk_indicator_sources"),
    )
    op.create_index("idx_indicator_sources_document", "indicator_sources", ["document_id"], unique=False)

    op.create_table(
        "ingestion_retry_queue",
        sa.Column("retry_id", UUID_TYPE, primary_key=True),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("backend", sa.Text(), nullable=False),
        sa.Column("payload_json", JSON_TYPE, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_retry_queue_case_backend", "ingestion_retry_queue", ["case_id", "backend"], unique=False)


def downgrade() -> None:
    """Drop dual-write ingestion tables."""

    op.drop_index("idx_retry_queue_case_backend", table_name="ingestion_retry_queue")
    op.drop_table("ingestion_retry_queue")

    op.drop_index("idx_indicator_sources_document", table_name="indicator_sources")
    op.drop_table("indicator_sources")

    op.drop_index("idx_indicators_last_seen_at", table_name="indicators")
    op.drop_index("idx_indicators_case_id", table_name="indicators")
    op.drop_index("idx_indicators_category_number", table_name="indicators")
    op.drop_table("indicators")

    op.drop_index("idx_entity_mentions_document", table_name="entity_mentions")
    op.drop_table("entity_mentions")

    op.drop_index("idx_entities_type_value", table_name="entities")
    op.drop_table("entities")

    op.drop_index("idx_documents_case", table_name="source_documents")
    op.drop_table("source_documents")

    op.drop_index("idx_cases_status", table_name="cases")
    op.drop_index("idx_cases_classification", table_name="cases")
    op.drop_index("idx_cases_dataset_reported_at", table_name="cases")
    op.drop_table("cases")

    op.drop_index("idx_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("idx_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
