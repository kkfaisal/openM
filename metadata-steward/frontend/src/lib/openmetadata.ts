// OpenMetadata UI URL helpers.
export const OM_UI_BASE = "http://localhost:8585";

export function omEntityUrl(entityType: string, fqn: string): string {
  return `${OM_UI_BASE}/${entityType}/${fqn}`;
}
