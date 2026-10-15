"""SQLAlchemy models.

Two logical groups:

* ``Catalog*`` — the simulated OpenMetadata system of record. In production
  these rows are owned by OpenMetadata; here they live in the demo catalog so
  the whole vertical slice can run without a live OpenMetadata deployment.
* Steward tables — the state the steward itself owns (findings,
  recommendations, approvals, audit events, policies, health snapshots, etc.).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Catalog (OpenMetadata system of record, simulated for demo mode)
# --------------------------------------------------------------------------- #
class MetadataTool(Base):
    """A metadata-management tool connection (OpenMetadata, Amundsen, DataHub,
    Atlan, Collibra, Alation, Unity Catalog, ...). Datasets belong to a tool."""

    __tablename__ = "metadata_tools"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)  # openmetadata | amundsen | datahub | ...
    host: Mapped[str | None] = mapped_column(String(256), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="CONNECTED")  # CONNECTED | PENDING | ERROR
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    tables: Mapped[list["CatalogTable"]] = relationship(back_populates="tool")
    datasets: Mapped[list["ToolDataset"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ToolDataset(Base):
    """An OpenMetadata database imported into MetaLens as a dataset.

    The dataset key (``service.database``) is what findings, ingestions and the
    RAG index are attached to. ``schemas`` optionally limits the sync to some
    schemas; empty means all.
    """

    __tablename__ = "tool_datasets"
    __table_args__ = (UniqueConstraint("tool_id", "dataset_key", name="uq_tool_dataset"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tool_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_tools.id", ondelete="CASCADE"), index=True
    )
    service_name: Mapped[str] = mapped_column(String(256))
    database_name: Mapped[str] = mapped_column(String(256))
    dataset_key: Mapped[str] = mapped_column(String(512), index=True)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    schemas: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING | SYNCED | ERROR
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    tool: Mapped["MetadataTool"] = relationship(back_populates="datasets")


class CatalogDomain(Base):
    __tablename__ = "catalog_domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    tables: Mapped[list["CatalogTable"]] = relationship(back_populates="domain")


class CatalogTeam(Base):
    __tablename__ = "catalog_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    domain_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_domains.id"), nullable=True
    )


class CatalogGlossaryTerm(Base):
    __tablename__ = "catalog_glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)


class CatalogTable(Base):
    __tablename__ = "catalog_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fqn: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    service_name: Mapped[str] = mapped_column(String(128), default="Snowflake")
    database_name: Mapped[str] = mapped_column(String(128), default="ANALYTICS")
    schema_name: Mapped[str] = mapped_column(String(128))
    tool_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_tools.id", ondelete="SET NULL"), nullable=True, index=True
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_teams.id"), nullable=True
    )
    domain_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_domains.id"), nullable=True
    )
    tags: Mapped[list] = mapped_column(JSON, default=list)

    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_queried_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    domain: Mapped["CatalogDomain"] = relationship(back_populates="tables")
    owner: Mapped["CatalogTeam"] = relationship()
    tool: Mapped["MetadataTool | None"] = relationship(back_populates="tables")
    columns: Mapped[list["CatalogColumn"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )


class CatalogColumn(Base):
    __tablename__ = "catalog_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_tables.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    data_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)

    table: Mapped["CatalogTable"] = relationship(back_populates="columns")


# --------------------------------------------------------------------------- #
# Steward state
# --------------------------------------------------------------------------- #
class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM", index=True)
    entity: Mapped[str] = mapped_column(String(256), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="table")
    domain: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    finding_id: Mapped[str | None] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    finding: Mapped["Finding"] = relationship(back_populates="evidence")
    recommendation: Mapped["Recommendation"] = relationship(back_populates="evidence")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(64))  # description / owner / domain ...
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_mode: Mapped[str] = mapped_column(
        String(24), default="REQUIRE_APPROVAL"
    )  # AUTO_APPLY | REQUIRE_APPROVAL | INFORMATION_ONLY | DENY
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    context_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    finding: Mapped["Finding"] = relationship(back_populates="recommendations")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(16))  # APPROVED | REJECTED | MODIFIED
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(128), default="Data Steward")
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MetadataChange(Base):
    __tablename__ = "metadata_changes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    entity: Mapped[str] = mapped_column(String(256), index=True)
    field: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    applied_by: Mapped[str] = mapped_column(String(128), default="steward")
    rollback_value: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    actor_type: Mapped[str] = mapped_column(String(16), default="system")
    actor: Mapped[str] = mapped_column(String(128), default="steward")
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str | None] = mapped_column(String(256), nullable=True)
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    finding_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    field: Mapped[str] = mapped_column(String(64))
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    action_mode: Mapped[str] = mapped_column(String(24))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    overall: Mapped[float] = mapped_column(Float, default=0.0)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tables_scanned: Mapped[int] = mapped_column(Integer, default=0)
    findings_created: Mapped[int] = mapped_column(Integer, default=0)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class DatasetContext(Base):
    """Plain-text, editable business context + per-agent instructions for a
    dataset (a database). Versioned so every regeneration is traceable."""

    __tablename__ = "dataset_contexts"

    # Key is "service.database" (e.g. "ecommerce_postgres.ecommerce").
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    table_instructions: Mapped[str] = mapped_column(Text, default="")
    column_instructions: Mapped[str] = mapped_column(Text, default="")
    dataset_instructions: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="user")  # user | ai
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )


class DatasetContextVersion(Base):
    """Immutable history of dataset context + instruction versions."""

    __tablename__ = "dataset_context_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(256), index=True)
    version: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    table_instructions: Mapped[str] = mapped_column(Text, default="")
    column_instructions: Mapped[str] = mapped_column(Text, default="")
    dataset_instructions: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# --------------------------------------------------------------------------- #
# Metadata sources (channels of unstructured/structured metadata)
# --------------------------------------------------------------------------- #
class MetadataSource(Base):
    """A connected metadata channel under a dataset (service.database).

    Examples: a Slack workspace/group, a Teams chat, an uploaded CSV/Excel
    data-dictionary, or a JSON export. The ``kind`` is the channel; the
    ``connection`` is how it was connected (``upload`` or ``api``).
    """

    __tablename__ = "metadata_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    dataset_key: Mapped[str] = mapped_column(String(256), index=True)
    name: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(32))  # slack | teams | csv | excel | json
    connection: Mapped[str] = mapped_column(String(16), default="upload")  # upload | api
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING | INGESTED | EXTRACTED | ERROR
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    fact_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # CDC + scheduling (Slack/Teams API sources)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    cursor: Mapped[str | None] = mapped_column(String(64), nullable=True)  # watermark
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    facts: Mapped[list["ExtractedFact"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    summary: Mapped["SourceSummary | None"] = relationship(
        back_populates="source", cascade="all, delete-orphan", uselist=False
    )


class SourceDocument(Base):
    """One raw ingested item (a message, a spreadsheet row, a file body)."""

    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_sources.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="message")  # message | row | file
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    source: Mapped["MetadataSource"] = relationship(back_populates="documents")


class ExtractedFact(Base):
    """A structured metadata fact extracted (by AI) from a source's content.

    Kept visible to the user and later used as evidence by the description and
    classification agents.
    """

    __tablename__ = "extracted_facts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_sources.id", ondelete="CASCADE"), index=True
    )
    dataset_key: Mapped[str] = mapped_column(String(256), index=True)
    category: Mapped[str] = mapped_column(
        String(32), default="general"
    )  # description | classification | owner | domain | glossary | lineage | general
    entity: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    statement: Mapped[str] = mapped_column(Text)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    source: Mapped["MetadataSource"] = relationship(back_populates="facts")


class SourceSummary(Base):
    """Human-readable AI summary of a source (what metadata it revealed)."""

    __tablename__ = "source_summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_sources.id", ondelete="CASCADE"), unique=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    key_points: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(16), default="heuristic")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    source: Mapped["MetadataSource"] = relationship(back_populates="summary")
