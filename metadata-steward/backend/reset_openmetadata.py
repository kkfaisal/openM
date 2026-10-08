"""Reset all steward demo entities in OpenMetadata (dev utility).

Deletes the Snowflake demo and the ecommerce Postgres demo (services,
databases, schemas, tables, domains, teams, glossary and the "Sensitive"
classification). Use with care — this performs hard deletes.
"""
from __future__ import annotations

from app.services.openmetadata_client import OpenMetadataClient
from app.services import demo_data as dd
from app.services import ecommerce as ec


def reset(client: OpenMetadataClient) -> None:
    # Tables → schemas → databases → services
    tables = client.list_tables()
    for t in tables:
        fqn = t.get("fullyQualifiedName") or ""
        if fqn.startswith("demo_snowflake.") or fqn.startswith(f"{ec.SERVICE_NAME}."):
            client.delete("tables", t["id"])

    for service_prefix, service_name in (
        ("demo_snowflake", "demo_snowflake"),
        (ec.SERVICE_NAME, ec.SERVICE_NAME),
    ):
        # schemas under the service's databases
        for schema in client.list_all("databaseSchemas"):
            sfqn = schema.get("fullyQualifiedName") or ""
            if sfqn.startswith(f"{service_name}."):
                client.delete("databaseSchemas", schema["id"])
        for db in client.list_all("databases"):
            dfqn = db.get("fullyQualifiedName") or ""
            if dfqn.startswith(f"{service_name}."):
                client.delete("databases", db["id"])
        svc = client.get_by_name("services/databaseServices", service_name)
        if svc:
            client.delete("services/databaseServices", svc["id"])

    # Domains / teams (union of both demos)
    domains = {d[0] for d in dd.DOMAINS} | {d[0] for d in ec.DOMAINS}
    for name in domains:
        dom = client.get_by_name("domains", name)
        if dom:
            client.delete("domains", dom["id"])

    teams = set(dd.TEAMS) | set(ec.TEAMS)
    for name in teams:
        team = client.get_by_name("teams", name)
        if team:
            client.delete("teams", team["id"])

    gl = client.get_by_name("glossaries", "Business Glossary")
    if gl:
        for term in client.list_glossary_terms():
            tfqn = term.get("fullyQualifiedName") or ""
            if tfqn.startswith("Business Glossary."):
                client.delete("glossaryTerms", term["id"])
        client.delete("glossaries", gl["id"])

    cls = client.get_by_name("classifications", "Sensitive")
    if cls:
        for tag in client.list_tags():
            tag_fqn = tag.get("fullyQualifiedName") or ""
            if tag_fqn.startswith("Sensitive."):
                try:
                    client.delete("tags", tag["id"])
                except Exception:  # noqa: BLE001
                    pass
        client.delete("classifications", cls["id"])

    print("Reset complete.")


if __name__ == "__main__":
    reset(OpenMetadataClient())
