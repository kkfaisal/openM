import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Cable,
  ChevronRight,
  Copy,
  Database,
  FileSpreadsheet,
  FileText,
  FileUp,
  MessageSquare,
  Mic,
  Plus,
  Webhook,
} from "lucide-react";
import { api } from "../api";
import { ConnectModal, type ConnectMode } from "../components/ConnectModal";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import type { Dataset, SourceRef } from "../types";

export function kindLabel(kind: string): string {
  const map: Record<string, string> = {
    slack: "Slack",
    teams: "Teams",
    csv: "CSV",
    excel: "Excel",
    json: "JSON",
    webhook: "Webhook",
    audio: "Audio",
    video: "Video",
  };
  return map[kind] ?? kind;
}

interface Connector {
  kind: string;
  label: string;
  desc: string;
  mode: ConnectMode;
  icon: typeof MessageSquare;
}

const CONNECTORS: Connector[] = [
  {
    kind: "slack",
    label: "Slack",
    desc: "Connect a Slack channel and pull its conversations via the Slack API.",
    mode: "slack",
    icon: MessageSquare,
  },
  {
    kind: "teams",
    label: "Microsoft Teams",
    desc: "Connect a Teams chat and pull messages via Microsoft Graph.",
    mode: "teams",
    icon: MessageSquare,
  },
  {
    kind: "csv",
    label: "CSV",
    desc: "Upload a CSV file (e.g. a data dictionary or column inventory).",
    mode: "upload",
    icon: FileText,
  },
  {
    kind: "excel",
    label: "Excel",
    desc: "Upload an .xlsx spreadsheet of structured metadata.",
    mode: "upload",
    icon: FileSpreadsheet,
  },
  {
    kind: "json",
    label: "JSON / Slack export",
    desc: "Upload JSON, or a Slack export ZIP, and let the steward parse it.",
    mode: "upload",
    icon: FileUp,
  },
  {
    kind: "audio",
    label: "Audio / Video",
    desc: "Upload a meeting recording — we transcribe it and extract the metadata discussed.",
    mode: "upload",
    icon: Mic,
  },
];

export default function Sources() {
  const { data, loading, error, reload } = useAsync(() => api.datasets(), []);
  const [connect, setConnect] = useState<{
    dataset: Dataset | null;
    mode: ConnectMode;
  } | null>(null);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const datasets = data ?? [];

  function openConnect(mode: ConnectMode, dataset?: Dataset) {
    if (datasets.length === 0) return;
    setConnect({ dataset: dataset ?? datasets[0], mode });
  }

  return (
    <div>
      <p className="muted" style={{ marginTop: 0, marginBottom: 16 }}>
        Ingest unstructured and structured metadata from Slack, Teams, CSV,
        Excel, JSON and webhooks. The steward ingests the raw content, extracts
        and summarizes the relevant metadata with AI, and feeds it into table
        and column descriptions &amp; classifications.
      </p>

      <div className="flag" style={{ marginBottom: 8 }}>AVAILABLE INGESTIONS</div>
      <div className="grid cols-3" style={{ marginBottom: 20 }}>
        {CONNECTORS.map((c) => (
          <div key={c.kind} className="card" style={{ marginBottom: 0 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <div className="stat-icon" style={{ background: "#efe9f8" }}>
                <c.icon size={18} color="#7b5fc7" />
              </div>
              <div style={{ flex: 1 }}>
                <div className="card-title" style={{ fontSize: 14 }}>{c.label}</div>
                <div className="card-sub" style={{ fontSize: 12 }}>{c.desc}</div>
              </div>
            </div>
            <button
              className="btn btn-primary btn-sm"
              style={{ marginTop: 10, width: "100%" }}
              onClick={() => openConnect(c.mode)}
              disabled={datasets.length === 0}
            >
              <Plus size={15} /> Add
            </button>
          </div>
        ))}
      </div>

      {datasets.length > 0 && (
        <>
          <div className="flag" style={{ marginBottom: 8 }}>WEBHOOKS — POST DATA IN</div>
          <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
            Each dataset has a webhook URL. POST a JSON body with a{" "}
            <code>{"{\"text\": \"...\"}"}</code> field to push metadata straight
            into the tool (it is ingested and extracted like any other source).
          </p>
          {datasets.map((ds) => (
            <WebhookCard key={ds.key} dataset={ds} />
          ))}
        </>
      )}

      <div className="flag" style={{ marginBottom: 8 }}>INGESTIONS</div>
      {datasets.length === 0 ? (
        <EmptyState text="No datasets synced yet — sync a dataset before adding ingestions." />
      ) : (
        datasets.map((ds) => (
          <DatasetSources
            key={ds.key}
            dataset={ds}
            onConnect={() => openConnect("upload", ds)}
          />
        ))
      )}

      {connect && (
        <ConnectModal
          datasets={datasets}
          initialDataset={connect.dataset}
          initialMode={connect.mode}
          onClose={() => setConnect(null)}
          onDone={reload}
        />
      )}
    </div>
  );
}

function DatasetSources({
  dataset,
  onConnect,
}: {
  dataset: Dataset;
  onConnect: () => void;
}) {
  const sources = dataset.sources ?? [];
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Database size={18} color="#7b5fc7" />
        <div style={{ flex: 1, minWidth: 140 }}>
          <div className="card-title" style={{ fontSize: 16 }}>{dataset.database}</div>
          <div className="card-sub mono">{dataset.key}</div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={onConnect}>
          <Plus size={15} /> Add ingestion
        </button>
      </div>

      {sources.length === 0 ? (
        <div className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          No ingestions yet. Add Slack, Teams, CSV, Excel, JSON or a webhook to
          start extracting metadata.
        </div>
      ) : (
        <div style={{ marginTop: 12 }}>
          {sources.map((s) => (
            <SourceRow key={s.id} source={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceRow({ source }: { source: SourceRef }) {
  return (
    <Link
      to={`/sources/${source.id}`}
      className="row-link"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 8px",
        borderBottom: "1px dashed #e4dcf1",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <Cable size={16} color="#8a80a6" />
      <div style={{ minWidth: 160 }}>
        <div style={{ fontWeight: 600, fontSize: 13.5 }}>{source.name}</div>
        <div className="muted" style={{ fontSize: 11.5 }}>
          {source.connection === "api" ? "API" : "upload"}
        </div>
      </div>
      <span className="badge field">{kindLabel(source.kind)}</span>
      <StatusBadge status={source.status} />
      {source.schedule_enabled && (
        <span className="badge status-RESOLVED">Scheduled</span>
      )}
      <span className="muted" style={{ fontSize: 12 }}>
        {source.document_count} docs · {source.fact_count} facts
      </span>
      <ChevronRight size={16} color="#b1a8c9" />
    </Link>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "EXTRACTED"
      ? "status-RESOLVED"
      : status === "ERROR"
      ? "sev-HIGH"
      : status === "INGESTED"
      ? "mode-INFORMATION_ONLY"
      : "sev-MEDIUM";
  return <span className={`badge ${cls}`}>{status}</span>;
}

function WebhookCard({ dataset }: { dataset: Dataset }) {
  const url = `${window.location.origin}/api/webhooks/${encodeURIComponent(dataset.key)}`;
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="card" style={{ marginBottom: 12, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Webhook size={18} color="#7b5fc7" />
        <div style={{ flex: 1, minWidth: 220 }}>
          <div className="card-title" style={{ fontSize: 14 }}>{dataset.database}</div>
          <div className="card-sub mono" style={{ fontSize: 12, wordBreak: "break-all" }}>{url}</div>
        </div>
        <button className="btn btn-sm" onClick={copy}>
          <Copy size={15} /> {copied ? "Copied ✓" : "Copy URL"}
        </button>
      </div>
      <p className="muted" style={{ fontSize: 12.5, margin: "10px 0 6px" }}>
        Point a Teams outgoing webhook / Power Automate flow, or a Slack Events
        API subscription, at this URL. Payloads are auto-detected.
      </p>
      <pre
        style={{
          fontSize: 12,
          background: "#f6f2fb",
          border: "1px solid #e4dcf1",
          borderRadius: 8,
          padding: 10,
          overflow: "auto",
          margin: "0 0 10px",
        }}
      >
{`# simple / Teams
curl -X POST '${url}' -H 'Content-Type: application/json' \\
  -d '{"text": "card_number is a raw PAN and must be tokenized", "from": {"user": {"displayName": "Priya"}}}'

# Slack Events API message
curl -X POST '${url}' -H 'Content-Type: application/json' \\
  -d '{"type": "event_callback", "event": {"type": "message", "text": "customer_id is the unique identifier", "user": "U123", "channel": "C456"}}'`}
      </pre>
    </div>
  );
}
