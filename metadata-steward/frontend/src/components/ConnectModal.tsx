import { useState } from "react";
import { FileUp, Loader2, MessageSquare, RefreshCw, X } from "lucide-react";
import { api } from "../api";
import type { Dataset } from "../types";

export type ConnectMode = "upload" | "slack" | "teams";

export function ConnectModal({
  datasets,
  initialDataset,
  initialMode,
  onClose,
  onDone,
}: {
  datasets: Dataset[];
  initialDataset: Dataset | null;
  initialMode: ConnectMode;
  onClose: () => void;
  onDone: () => void;
}) {
  const [datasetKey, setDatasetKey] = useState(initialDataset?.key ?? datasets[0]?.key ?? "");
  const [mode, setMode] = useState<ConnectMode>(initialMode);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [token, setToken] = useState("");
  const [channelId, setChannelId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedInterval, setSchedInterval] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function errText(e: unknown): string {
    const raw = e instanceof Error ? e.message : String(e);
    const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
    return m ? m[1] : raw;
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (mode === "upload") {
        if (!file) throw new Error("Choose a file to upload.");
        await api.uploadSource(datasetKey, name || file.name, file);
      } else if (mode === "slack") {
        await api.connectSource(datasetKey, {
          name: name || "Slack workspace",
          kind: "slack",
          connection: "api",
          config: { token, channel_id: channelId },
          schedule_enabled: schedEnabled,
          interval_minutes: schedInterval,
        });
      } else {
        await api.connectSource(datasetKey, {
          name: name || "Teams chat",
          kind: "teams",
          connection: "api",
          config: { token, team_id: teamId, channel_id: channelId },
          schedule_enabled: schedEnabled,
          interval_minutes: schedInterval,
        });
      }
      onDone();
      onClose();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="card-title" style={{ fontSize: 16 }}>
              Add a metadata ingestion
            </div>
            <div className="card-sub">Choose a dataset and an ingestion type</div>
          </div>
          <button className="btn btn-sm" onClick={onClose}>
            <X size={15} /> Close
          </button>
        </div>

        <label className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Dataset</label>
        <select
          className="input"
          style={{ width: "100%", margin: "4px 0 12px" }}
          value={datasetKey}
          onChange={(e) => setDatasetKey(e.target.value)}
        >
          {datasets.map((d) => (
            <option key={d.key} value={d.key}>{d.database} ({d.key})</option>
          ))}
        </select>

        <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
          {(["upload", "slack", "teams"] as const).map((m) => (
            <button
              key={m}
              className={`btn btn-sm ${mode === m ? "btn-primary" : ""}`}
              onClick={() => setMode(m)}
            >
              {m === "upload" ? <FileUp size={15} /> : <MessageSquare size={15} />}
              {m === "upload" ? "Upload file" : m === "slack" ? "Slack" : "Teams"}
            </button>
          ))}
        </div>

        <label className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Name</label>
        <input
          className="input"
          style={{ width: "100%", margin: "4px 0 12px" }}
          placeholder={mode === "upload" ? "e.g. Data dictionary v2" : mode === "slack" ? "e.g. #data-governance" : "e.g. Data Platform chat"}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        {mode === "upload" && (
          <div style={{ marginBottom: 12 }}>
            <label className="muted" style={{ fontSize: 12, fontWeight: 600 }}>File (CSV, XLSX, JSON, Slack export ZIP, audio/video)</label>
            <input
              type="file"
              accept=".csv,.xlsx,.xls,.json,.zip,.mp3,.wav,.m4a,.flac,.ogg,.aac,.mp4,.mov,.webm,.mkv,.m4v,.avi"
              style={{ margin: "4px 0" }}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        )}

        {mode !== "upload" && (
          <>
            <label className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Access token</label>
            <input
              className="input"
              type="password"
              style={{ width: "100%", margin: "4px 0 12px" }}
              placeholder={mode === "slack" ? "xoxb-..." : "Graph access token"}
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            {mode === "teams" && (
              <>
                <label className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Team ID</label>
                <input
                  className="input"
                  style={{ width: "100%", margin: "4px 0 12px" }}
                  placeholder="team guid"
                  value={teamId}
                  onChange={(e) => setTeamId(e.target.value)}
                />
              </>
            )}
            <label className="muted" style={{ fontSize: 12, fontWeight: 600 }}>Channel ID</label>
            <input
              className="input"
              style={{ width: "100%", margin: "4px 0 12px" }}
              placeholder={mode === "slack" ? "C0123456789" : "channel guid"}
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={schedEnabled}
                  onChange={(e) => setSchedEnabled(e.target.checked)}
                />
                Schedule automatic (CDC) syncs
              </label>
              {schedEnabled && (
                <label className="muted" style={{ fontSize: 12.5 }}>
                  every{" "}
                  <input
                    className="input"
                    type="number"
                    min={1}
                    style={{ width: 72, display: "inline-block", margin: "0 4px" }}
                    value={schedInterval}
                    onChange={(e) => setSchedInterval(Math.max(1, Number(e.target.value) || 60))}
                  />{" "}
                  minutes
                </label>
              )}
            </div>
            <p className="muted" style={{ fontSize: 12, margin: "0 0 12px" }}>
              The token is stored with the source (masked in the API) so
              scheduled CDC syncs can keep pulling new messages automatically.
            </p>
          </>
        )}

        {error && (
          <div
            style={{
              background: "#fbe8e6",
              border: "1px solid #eec9c6",
              borderRadius: 8,
              padding: "8px 10px",
              color: "#c14a43",
              fontSize: 12.5,
              marginBottom: 12,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn btn-success" onClick={submit} disabled={busy}>
            {busy ? <Loader2 size={15} className="spinner" /> : <RefreshCw size={15} />}
            {busy ? "Ingesting…" : "Ingest & extract"}
          </button>
        </div>
      </div>
    </div>
  );
}
