// Formatting + label helpers.

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function titleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function humanAction(action: string): string {
  return titleCase(action.replace(/_/g, " "));
}

export const FINDING_TYPE_LABELS: Record<string, string> = {
  MISSING_DESCRIPTION: "Missing description",
  POOR_DESCRIPTION: "Poor description",
  MISSING_COLUMN_DESCRIPTION: "Missing column description",
  MISSING_OWNER: "Missing owner",
  MISSING_DOMAIN: "Missing domain",
  MISSING_CLASSIFICATION: "Missing classification",
  POSSIBLE_PII: "Possible PII",
  STALE_ENTITY: "Stale entity",
};

export function findingLabel(type: string): string {
  return FINDING_TYPE_LABELS[type] ?? titleCase(type);
}

export function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function fieldLabel(field: string): string {
  return titleCase(field.replace("column.", "").replace(".classification", ""));
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.round(h / 24);
  if (days < 7) return `${days}d ago`;
  return fmtDateShort(iso);
}

/** Pull FastAPI's `detail` message out of an API error, if present. */
export function errorDetail(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
  return m ? m[1] : raw;
}
