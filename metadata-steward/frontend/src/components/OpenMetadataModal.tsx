import { ExternalLink, X } from "lucide-react";

export default function OpenMetadataModal({
  url,
  title,
  onClose,
}: {
  url: string | null;
  title: string;
  onClose: () => void;
}) {
  if (!url) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ minWidth: 0 }}>
            <div className="card-title" style={{ fontSize: 16 }}>
              {title} — OpenMetadata
            </div>
            <div
              className="card-sub mono"
              style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
            >
              {url}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <a className="btn btn-sm" href={url} target="_blank" rel="noreferrer">
              <ExternalLink size={15} /> Open in tab
            </a>
            <button className="btn btn-sm" onClick={onClose}>
              <X size={15} /> Close
            </button>
          </div>
        </div>
        <iframe
          src={url}
          title="OpenMetadata"
          style={{
            width: "100%",
            height: "72vh",
            border: "1px solid #e4dcf1",
            borderRadius: 10,
            background: "#fff",
          }}
        />
      </div>
    </div>
  );
}
