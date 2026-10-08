// Shared API types (mirror backend schemas).

export interface Finding {
  id: string;
  type: string;
  severity: string;
  entity: string;
  entity_type: string;
  domain: string | null;
  status: string;
  summary: string | null;
  agent: string | null;
  detected_at: string;
  resolved_at: string | null;
}

export interface Evidence {
  id: string;
  type: string;
  value: string;
  source: string | null;
  created_at: string;
}

export interface Recommendation {
  id: string;
  finding_id: string;
  field: string;
  old_value: string | null;
  new_value: string | null;
  confidence: number;
  reasoning_summary: string | null;
  action_mode: string;
  status: string;
  created_at: string;
  resolved_at: string | null;
  policy_id: string | null;
  version: number;
  context_snapshot: string | null;
  evidence: Evidence[];
}

export interface FindingDetail extends Finding {
  evidence: Evidence[];
  recommendations: Recommendation[];
}

export interface AgentRun {
  id: string;
  agent_name: string;
  finding_id: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  steps: { step: string; detail: string; ok: boolean }[];
  summary: string | null;
  result_json: Record<string, unknown> | null;
}

export interface MetadataChange {
  id: string;
  entity: string;
  field: string;
  old_value: string | null;
  new_value: string | null;
  recommendation_id: string | null;
  applied_at: string;
  verified: boolean;
  applied_by: string;
}

export interface AuditEvent {
  id: string;
  actor_type: string;
  actor: string;
  action: string;
  entity: string | null;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  detail: string | null;
  confidence: number | null;
  policy: string | null;
  timestamp: string;
}

export interface Policy {
  id: string;
  name: string;
  description: string | null;
  field: string;
  conditions: Record<string, unknown>;
  action_mode: string;
  priority: number;
  enabled: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CatalogColumn {
  id: number;
  name: string;
  data_type: string;
  description: string | null;
  classification: string | null;
  tags: string[];
  position: number;
}

export interface CatalogTable {
  id: number;
  fqn: string;
  name: string;
  service_name: string;
  database_name: string;
  schema_name: string;
  description: string | null;
  domain: string | null;
  owner: string | null;
  tags: string[];
  row_count: number | null;
  last_queried_at: string | null;
  columns: CatalogColumn[];
}

export interface CatalogDomain {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
}

export interface OverviewStats {
  health: number;
  health_delta: number;
  total_tables: number;
  total_columns: number;
  open_findings: number;
  findings_by_severity: Record<string, number>;
  findings_by_type: Record<string, number>;
  pending_approvals: number;
  auto_resolved: number;
  recommendations_total: number;
  agent_runs: number;
  changes_last_7d: number;
  stale_assets: number;
  sensitive_findings: number;
  domains: {
    name: string;
    display_name: string;
    tables: number;
    missing_owner: number;
    missing_description: number;
  }[];
  recent_actions: {
    id: string;
    action: string;
    actor: string;
    entity: string | null;
    field: string | null;
    new_value: string | null;
    timestamp: string;
  }[];
  trend: { overall: number; created_at: string }[];
}

export interface HealthOut {
  id: string;
  overall: number;
  dimensions: Record<string, number>;
  created_at: string;
}

export interface SettingOut {
  key: string;
  value: Record<string, unknown>;
}

export interface PromptPreview {
  system_prompt: string;
  user_prompt: string;
  provider: string;
  model: string;
}

export interface PromptOverride {
  system_prompt?: string;
  user_prompt?: string;
}

export interface DatasetContext {
  key: string;
  description: string;
  table_instructions: string;
  column_instructions: string;
  dataset_instructions: string;
  source: string;
  version: number;
  updated_at: string | null;
}

export interface DatasetContextVersion {
  version: number;
  description: string;
  table_instructions: string;
  column_instructions: string;
  dataset_instructions: string;
  source: string;
  created_at: string | null;
}

export interface FindingRef {
  id: string;
  type: string;
  entity: string;
}

export interface DatasetTableRef {
  fqn: string;
  name: string;
  description: string | null;
  owner: string | null;
  domain: string | null;
  column_count: number;
  findings: FindingRef[];
}

export interface DatasetSchemaRef {
  name: string;
  tables: DatasetTableRef[];
}

export interface DatasetMetrics {
  health: number;
  tables: number;
  columns: number;
  described_tables: number;
  described_columns: number;
  open_findings: number;
  pending_approvals: number;
  auto_resolved: number;
  findings_by_severity: Record<string, number>;
  findings_by_type: Record<string, number>;
}

export interface Dataset {
  key: string;
  service: string;
  database: string;
  tool_id: string | null;
  tool_name: string | null;
  tool_type: string | null;
  schemas: DatasetSchemaRef[];
  context: DatasetContext | null;
  metrics: DatasetMetrics;
  sources: SourceRef[];
}

export interface MetadataTool {
  id: string;
  name: string;
  type: string;
  host: string | null;
  config: Record<string, unknown>;
  status: string;
  is_default: boolean;
  dataset_count: number;
  created_at: string;
  updated_at: string;
}

export interface SourceRef {
  id: string;
  name: string;
  kind: string;
  connection: string;
  status: string;
  document_count: number;
  fact_count: number;
  schedule_enabled: boolean;
  last_sync_at: string | null;
  updated_at: string | null;
}

export interface SourceSummary {
  id: string;
  source_id: string;
  summary: string;
  key_points: string[];
  provider: string;
  generated_at: string;
}

export interface Source extends SourceRef {
  dataset_key: string;
  config: Record<string, unknown>;
  error: string | null;
  interval_minutes: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
  created_at: string;
  updated_at: string;
  summary: SourceSummary | null;
}

export interface SourceDocument {
  id: string;
  source_id: string;
  external_id: string | null;
  kind: string;
  author: string | null;
  channel: string | null;
  ts: string | null;
  content: string;
  meta: Record<string, unknown>;
  ingested_at: string;
}

export interface ExtractedFact {
  id: string;
  source_id: string;
  dataset_key: string;
  category: string;
  entity: string | null;
  statement: string;
  evidence_text: string | null;
  confidence: number;
  document_ids: string[];
  created_at: string;
}

export interface SourceDetail extends Source {
  facts: ExtractedFact[];
  documents: SourceDocument[];
}

export interface RegenerationChange {
  entity: string;
  field: string;
  old_value: string | null;
  old_version: number;
  new_value: string | null;
  new_version: number;
}

export interface RegenerationResult {
  regenerated: number;
  changes: RegenerationChange[];
}
