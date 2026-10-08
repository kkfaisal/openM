"""Pydantic response/request schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Catalog ----
class CatalogColumnOut(ORMModel):
    id: int
    name: str
    data_type: str
    description: str | None
    classification: str | None
    tags: list
    position: int


class CatalogTableOut(ORMModel):
    id: int
    fqn: str
    name: str
    service_name: str
    database_name: str
    schema_name: str
    description: str | None
    domain: str | None
    owner: str | None
    tags: list
    row_count: int | None
    last_queried_at: datetime | None
    columns: list[CatalogColumnOut] = []


class CatalogDomainOut(ORMModel):
    id: int
    name: str
    display_name: str
    description: str | None


class GenerateDescriptionRequest(BaseModel):
    column: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None


class GenerateClassificationRequest(BaseModel):
    column: str
    system_prompt: str | None = None
    user_prompt: str | None = None


class RegenerateRequest(BaseModel):
    system_prompt: str | None = None
    user_prompt: str | None = None


class PromptPreviewRequest(BaseModel):
    kind: str  # table_description | column_description | classification
    fqn: str
    column: str | None = None


class PromptPreviewOut(BaseModel):
    system_prompt: str
    user_prompt: str
    provider: str
    model: str


# ---- Evidence ----
class EvidenceOut(ORMModel):
    id: str
    type: str
    value: str
    source: str | None
    created_at: datetime


# ---- Findings ----
class FindingOut(ORMModel):
    id: str
    type: str
    severity: str
    entity: str
    entity_type: str
    domain: str | None
    status: str
    summary: str | None
    agent: str | None
    detected_at: datetime
    resolved_at: datetime | None


class FindingDetail(FindingOut):
    evidence: list[EvidenceOut] = []
    recommendations: list["RecommendationOut"] = []


# ---- Recommendations ----
class RecommendationOut(ORMModel):
    id: str
    finding_id: str
    field: str
    old_value: str | None
    new_value: str | None
    confidence: float
    reasoning_summary: str | None
    action_mode: str
    status: str
    created_at: datetime
    resolved_at: datetime | None
    policy_id: str | None
    version: int
    context_snapshot: str | None
    evidence: list[EvidenceOut] = []


# ---- Approvals ----
class ApprovalOut(ORMModel):
    id: str
    recommendation_id: str
    decision: str
    comment: str | None
    modified_value: str | None
    decided_by: str
    decided_at: datetime


class ApprovalRequest(BaseModel):
    # `decision` is optional: the endpoint (approve/reject/modify) already
    # determines the decision, so the client doesn't need to send it.
    decision: str | None = None
    comment: str | None = None
    modified_value: str | None = None
    decided_by: str = "Data Steward"


# ---- Changes ----
class MetadataChangeOut(ORMModel):
    id: str
    entity: str
    field: str
    old_value: str | None
    new_value: str | None
    recommendation_id: str | None
    applied_at: datetime
    verified: bool
    applied_by: str


# ---- Audit ----
class AuditEventOut(ORMModel):
    id: str
    actor_type: str
    actor: str
    action: str
    entity: str | None
    field: str | None
    old_value: str | None
    new_value: str | None
    detail: str | None
    confidence: float | None
    policy: str | None
    timestamp: datetime


# ---- Agent runs ----
class AgentRunOut(ORMModel):
    id: str
    agent_name: str
    finding_id: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    steps: list
    summary: str | None
    result_json: dict | None


# ---- Policies ----
class PolicyOut(ORMModel):
    id: str
    name: str
    description: str | None
    field: str
    conditions: dict
    action_mode: str
    priority: int
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


class PolicyCreate(BaseModel):
    name: str
    description: str | None = None
    field: str
    conditions: dict
    action_mode: str
    priority: int = 100
    enabled: bool = True


class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    conditions: dict | None = None
    action_mode: str | None = None
    priority: int | None = None
    enabled: bool | None = None


# ---- Health ----
class HealthOut(ORMModel):
    id: str
    overall: float
    dimensions: dict
    created_at: datetime


# ---- Scans ----
class ScanRunOut(ORMModel):
    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    tables_scanned: int
    findings_created: int
    changes_detected: int


class ScanResult(BaseModel):
    scan: ScanRunOut
    findings_created: int


# ---- Overview / dashboard ----
class OverviewStats(BaseModel):
    health: float
    health_delta: float
    total_tables: int
    total_columns: int
    open_findings: int
    findings_by_severity: dict[str, int]
    findings_by_type: dict[str, int]
    pending_approvals: int
    auto_resolved: int
    recommendations_total: int
    agent_runs: int
    changes_last_7d: int
    stale_assets: int
    sensitive_findings: int
    domains: list[dict]
    recent_actions: list[dict]
    trend: list[dict]


# ---- Settings ----
class SettingOut(BaseModel):
    key: str
    value: dict


class SettingUpdate(BaseModel):
    value: dict


class OpenAIKeyUpdate(BaseModel):
    api_key: str = ""


# ---- Dataset hierarchy + context ----
class DatasetContextOut(BaseModel):
    key: str
    description: str
    table_instructions: str
    column_instructions: str
    dataset_instructions: str
    source: str
    version: int
    updated_at: datetime | None


class DatasetContextUpdate(BaseModel):
    description: str = ""
    table_instructions: str = ""
    column_instructions: str = ""
    dataset_instructions: str = ""
    source: str = "user"


class DatasetContextVersionOut(BaseModel):
    version: int
    description: str
    table_instructions: str
    column_instructions: str
    dataset_instructions: str
    source: str
    created_at: datetime | None


class RestoreContextRequest(BaseModel):
    version: int


class GenerateContextRequest(BaseModel):
    dataset_instructions: str = ""


class DatasetTableRef(BaseModel):
    fqn: str
    name: str
    description: str | None
    owner: str | None
    domain: str | None
    column_count: int
    findings: list["FindingRef"] = []


class FindingRef(BaseModel):
    id: str
    type: str
    entity: str


class DatasetSchemaRef(BaseModel):
    name: str
    tables: list[DatasetTableRef]


class DatasetMetrics(BaseModel):
    health: float
    tables: int
    columns: int
    described_tables: int = 0
    described_columns: int = 0
    open_findings: int
    pending_approvals: int
    auto_resolved: int
    findings_by_severity: dict[str, int]
    findings_by_type: dict[str, int]


class DatasetOut(BaseModel):
    key: str
    service: str
    database: str
    tool_id: str | None = None
    tool_name: str | None = None
    tool_type: str | None = None
    schemas: list[DatasetSchemaRef]
    context: DatasetContextOut | None
    metrics: DatasetMetrics
    sources: list["SourceRef"] = []


# ---- Metadata sources (channels) ----
class SourceRef(BaseModel):
    id: str
    name: str
    kind: str
    connection: str
    status: str
    document_count: int
    fact_count: int
    schedule_enabled: bool = False
    last_sync_at: datetime | None = None
    updated_at: datetime | None = None


class SourceDocumentOut(ORMModel):
    id: str
    source_id: str
    external_id: str | None
    kind: str
    author: str | None
    channel: str | None
    ts: datetime | None
    content: str
    meta: dict
    ingested_at: datetime


class ExtractedFactOut(ORMModel):
    id: str
    source_id: str
    dataset_key: str
    category: str
    entity: str | None
    statement: str
    evidence_text: str | None
    confidence: float
    document_ids: list
    created_at: datetime


class SourceSummaryOut(ORMModel):
    id: str
    source_id: str
    summary: str
    key_points: list
    provider: str
    generated_at: datetime


class SourceOut(SourceRef):
    dataset_key: str
    config: dict
    error: str | None
    interval_minutes: int
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime
    summary: SourceSummaryOut | None


class SourceDetail(SourceOut):
    facts: list[ExtractedFactOut] = []
    documents: list[SourceDocumentOut] = []


class SourceConnectRequest(BaseModel):
    name: str
    kind: str  # slack | teams
    connection: str = "api"
    config: dict = {}
    schedule_enabled: bool = False
    interval_minutes: int = 60


class SourceScheduleUpdate(BaseModel):
    enabled: bool
    interval_minutes: int = 60


class WebhookIngestRequest(BaseModel):
    text: str
    name: str = ""
    kind: str = "webhook"
    author: str | None = None
    channel: str | None = None


# ---- Metadata tools (connections) ----
class MetadataToolOut(BaseModel):
    id: str
    name: str
    type: str
    host: str | None
    config: dict
    status: str
    is_default: bool
    dataset_count: int
    created_at: datetime
    updated_at: datetime


class ToolCreate(BaseModel):
    name: str
    type: str
    host: str | None = None
    config: dict = {}
    seed_demo: bool = False


class SourceExtractResult(BaseModel):
    source: SourceOut
    documents: int
    facts: int


DatasetOut.model_rebuild()
FindingDetail.model_rebuild()
