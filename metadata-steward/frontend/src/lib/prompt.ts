import { useEffect, useState } from "react";
import { api } from "../api";
import type { FindingDetail } from "../types";

/** Whether the global "enable_prompt_editing" flag is currently on. */
export function usePromptEditing(): boolean {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    api
      .settings()
      .then((list) => {
        const row = list.find((s) => s.key === "enable_prompt_editing");
        setEnabled(Boolean(row?.value?.value));
      })
      .catch(() => setEnabled(false));
  }, []);
  return enabled;
}

/** Derive a prompt-preview target (kind + fqn + column) from a finding. */
export function promptTargetForFinding(f: FindingDetail): {
  kind: string;
  fqn: string;
  column?: string;
} {
  const kind =
    f.type === "MISSING_DESCRIPTION"
      ? "table_description"
      : f.type === "MISSING_COLUMN_DESCRIPTION"
      ? "column_description"
      : f.type === "MISSING_CLASSIFICATION"
      ? "classification"
      : "table_description";

  let fqn = f.entity;
  let column: string | undefined;
  if (f.entity_type === "column") {
    const idx = f.entity.lastIndexOf(".");
    fqn = f.entity.slice(0, idx);
    column = f.entity.slice(idx + 1);
  }
  return { kind, fqn, column };
}
