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

export interface ToolAuthInput {
  type: "jwt" | "basic" | "none";
  token?: string;
  email?: string;
  password?: string;
}

export interface ToolDataset {
  id: string;
  tool_id: string;
  service_name: string;
  database_name: string;
  dataset_key: string;
  display_name: string | null;
  schemas: string[];
  status: string;
  error: string | null;
  table_count: number;
  last_synced_at: string | null;
  created_at: string;
}

export interface MetadataTool {
  id: string;
  name: string;
  type: string;
  host: string | null;
  auth: { type: string; email: string | null; token_hint: string | null; has_secret: boolean };
  verify_ssl: boolean;
  status: string;
  last_error: string | null;
  last_checked_at: string | null;
  is_default: boolean;
  dataset_count: number;
  datasets: ToolDataset[];
  created_at: string;
  updated_at: string;
}

export interface ToolTestResult {
  ok: boolean;
  version: string | null;
  message: string;
  services: number | null;
}

export interface BrowseService {
  name: string;
  service_type: string | null;
  databases: {
    name: string;
    fqn: string;
    description: string | null;
    imported_by: string | null;
    imported_here: boolean;
  }[];
}

export interface BrowseSchema {
  name: string;
  fqn: string;
  table_count: number;
}

export interface DatasetImportResult {
  imported: ToolDataset[];
  errors: Record<string, string>;
  findings_created: number;
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

export interface RagStatus {
  enabled: boolean;
  backend: string;
  location: string;
  embedding_provider: string;
  embedding_model: string;
  collection: string;
  min_score: number;
  chunk_chars: number;
  ready: boolean;
  error: string | null;
  total_chunks: number;
}

export interface RagSourceStat {
  id: string;
  name: string;
  kind: string;
  status: string;
  document_count: number;
  fact_count: number;
  chunks: number;
  document_chunks: number;
  fact_chunks: number;
  index_error: string | null;
  updated_at: string;
}

export interface RagDatasetStat {
  dataset_key: string;
  chunks: number;
  sources: RagSourceStat[];
}

export interface RagHit {
  id: string;
  score: number;
  text: string;
  kind: "document" | "fact";
  dataset_key: string;
  source_id: string;
  source_name: string;
  source_kind: string;
  doc_id?: string;
  doc_kind?: string;
  author?: string | null;
  channel?: string | null;
  ts?: string | null;
  chunk_index?: number;
  entities: string[];
  category?: string;
  confidence?: number;
  evidence_text?: string | null;
}

export interface RagAnswer {
  question: string;
  answer: string;
  citations: RagHit[];
  mode: string;
}

export interface MlflowStatus {
  enabled: boolean;
  ready: boolean;
  tracking_uri: string | null;
  ui_url: string | null;
  experiment: string;
  experiment_id: string | null;
  eval_experiment: string;
  error: string | null;
}

export interface QualitySummary {
  window_days: number;
  totals: {
    agent_runs: number;
    failure_rate: number;
    reviewed: number;
    acceptance_rate: number | null;
    edit_rate: number | null;
    brier_score: number | null;
    calibration_error: number | null;
  };
  agents: {
    agent: string;
    runs: number;
    failed: number;
    failure_rate: number;
    latency_p50_s: number | null;
    latency_p95_s: number | null;
    traced: number;
  }[];
  fields: {
    field: string;
    recommendations: number;
    auto_applied: number;
    pending: number;
    reviewed: number;
    acceptance_rate: number | null;
    edit_rate: number | null;
    avg_confidence: number | null;
  }[];
  calibration: { bucket: string; count: number; mean_confidence: number; acceptance_rate: number }[];
  trend: { day: string; recommendations: number; accepted: number; rejected: number }[];
  recent_traces: {
    agent: string;
    finding_id: string | null;
    status: string;
    started_at: string;
    latency_s: number | null;
    trace_id: string;
    trace_url: string | null;
  }[];
  mlflow: MlflowStatus;
}

export interface EvalJob {
  id: string;
  suite: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  metrics: Record<string, number> | null;
  run_url: string | null;
  error: string | null;
}

export interface EvalRun {
  run_id: string;
  name: string;
  suite: string | null;
  status: string;
  start_time: number;
  metrics: Record<string, number>;
  params: Record<string, string>;
  url: string | null;
}
