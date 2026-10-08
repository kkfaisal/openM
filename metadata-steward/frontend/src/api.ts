// Thin typed API client.
import type {
  AgentRun,
  AuditEvent,
  CatalogDomain,
  CatalogTable,
  Dataset,
  DatasetContext,
  DatasetContextVersion,
  ExtractedFact,
  Finding,
  FindingDetail,
  HealthOut,
  MetadataChange,
  MetadataTool,
  OverviewStats,
  Policy,
  PromptOverride,
  PromptPreview,
  Recommendation,
  RegenerationResult,
  SettingOut,
  Source,
  SourceDetail,
  SourceDocument,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  overview: () => request<OverviewStats>("/overview"),

  health: () => request<HealthOut>("/health"),
  healthHistory: () => request<HealthOut[]>("/health/history"),

  findings: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return request<Finding[]>(`/findings${qs}`);
  },
  finding: (id: string) => request<FindingDetail>(`/findings/${id}`),
  investigate: (id: string) =>
    request<FindingDetail>(`/findings/${id}/investigate`, { method: "POST" }),
  regenerateFinding: (id: string, promptOverride?: PromptOverride) =>
    request<FindingDetail>(`/findings/${id}/regenerate`, {
      method: "POST",
      body: JSON.stringify(promptOverride ?? {}),
    }),

  recommendations: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return request<Recommendation[]>(`/recommendations${qs}`);
  },
  recommendApprove: (id: string, body: Record<string, unknown>) =>
    request<Recommendation>(`/recommendations/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  recommendReject: (id: string, body: Record<string, unknown>) =>
    request<Recommendation>(`/recommendations/${id}/reject`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  recommendModify: (id: string, body: Record<string, unknown>) =>
    request<Recommendation>(`/recommendations/${id}/modify`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  recommendSelect: (id: string) =>
    request<Recommendation>(`/recommendations/${id}/select`, {
      method: "POST",
    }),

  agentRuns: () => request<AgentRun[]>("/agent-runs"),
  changes: () => request<MetadataChange[]>("/changes"),
  audit: () => request<AuditEvent[]>("/audit"),
  policies: () => request<Policy[]>("/policies"),
  updatePolicy: (id: string, body: Record<string, unknown>) =>
    request<Policy>(`/policies/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  scan: () =>
    request<{ scan: { id: string; status: string }; findings_created: number }>(
      "/scans",
      { method: "POST" }
    ),

  tables: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return request<CatalogTable[]>(`/catalog/tables${qs}`);
  },
  table: (fqn: string) =>
    request<CatalogTable>(`/catalog/tables/${encodeURIComponent(fqn)}`),
  generateDescription: (fqn: string, column?: string, promptOverride?: PromptOverride) =>
    request<FindingDetail>(
      `/catalog/tables/${encodeURIComponent(fqn)}/generate-description`,
      {
        method: "POST",
        body: JSON.stringify({ column: column ?? null, ...(promptOverride ?? {}) }),
      }
    ),
  generateClassification: (fqn: string, column: string, promptOverride?: PromptOverride) =>
    request<FindingDetail>(
      `/catalog/tables/${encodeURIComponent(fqn)}/generate-classification`,
      {
        method: "POST",
        body: JSON.stringify({ column, ...(promptOverride ?? {}) }),
      }
    ),
  promptPreview: (body: { kind: string; fqn: string; column?: string }) =>
    request<PromptPreview>(`/llm/prompt-preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  domains: () => request<CatalogDomain[]>("/catalog/domains"),

  datasets: () => request<Dataset[]>("/datasets"),
  saveDatasetContext: (key: string, body: Record<string, unknown>) =>
    request<DatasetContext>(`/datasets/${encodeURIComponent(key)}/context`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  generateDatasetContext: (key: string, datasetInstructions: string = "") =>
    request<DatasetContext>(`/datasets/${encodeURIComponent(key)}/generate-context`, {
      method: "POST",
      body: JSON.stringify({ dataset_instructions: datasetInstructions }),
    }),
  datasetContextHistory: (key: string) =>
    request<DatasetContextVersion[]>(
      `/datasets/${encodeURIComponent(key)}/context/history`
    ),
  restoreDatasetContext: (key: string, version: number) =>
    request<DatasetContext>(
      `/datasets/${encodeURIComponent(key)}/context/restore`,
      { method: "POST", body: JSON.stringify({ version }) }
    ),
  regenerateDataset: (key: string) =>
    request<RegenerationResult>(`/datasets/${encodeURIComponent(key)}/regenerate`, {
      method: "POST",
    }),

  tools: () => request<MetadataTool[]>("/tools"),
  createTool: (body: Record<string, unknown>) =>
    request<MetadataTool>("/tools", { method: "POST", body: JSON.stringify(body) }),
  deleteTool: async (id: string) => {
    const res = await fetch(`${BASE}/tools/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
  },

  settings: () => request<SettingOut[]>("/settings"),
  saveSetting: (key: string, value: unknown) =>
    request<SettingOut>(`/settings/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  saveOpenAIKey: (apiKey: string) =>
    request<SettingOut>("/settings/openai_api_key", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey }),
    }),

  // ---- Metadata sources (channels) ----
  datasetSources: (key: string) =>
    request<Source[]>(`/datasets/${encodeURIComponent(key)}/sources`),
  uploadSource: async (key: string, name: string, file: File) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("file", file);
    const res = await fetch(`${BASE}/datasets/${encodeURIComponent(key)}/sources/upload`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
    return res.json() as Promise<Source>;
  },
  connectSource: (key: string, body: Record<string, unknown>) =>
    request<Source>(`/datasets/${encodeURIComponent(key)}/sources`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  source: (id: string) => request<SourceDetail>(`/sources/${id}`),
  sourceDocuments: (id: string, q?: string) => {
    const qs = q ? `?${new URLSearchParams({ q })}` : "";
    return request<SourceDocument[]>(`/sources/${id}/documents${qs}`);
  },
  sourceFacts: (id: string) => request<ExtractedFact[]>(`/sources/${id}/facts`),
  extractSource: (id: string) =>
    request<{ source: Source; documents: number; facts: number }>(
      `/sources/${id}/extract`,
      { method: "POST" }
    ),
  syncSource: (id: string) =>
    request<Source>(`/sources/${id}/sync`, { method: "POST" }),
  setSourceSchedule: (id: string, enabled: boolean, intervalMinutes: number) =>
    request<Source>(`/sources/${id}/schedule`, {
      method: "PUT",
      body: JSON.stringify({ enabled, interval_minutes: intervalMinutes }),
    }),
  deleteSource: async (id: string) => {
    const res = await fetch(`${BASE}/sources/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
  },
};
