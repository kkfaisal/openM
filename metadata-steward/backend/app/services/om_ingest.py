"""Ingest the demo catalog into a real OpenMetadata instance.

Idempotent: existing entities (matched by name/FQN) are reused, so it is safe
to run repeatedly and to point at an instance that already has some data.
"""
from __future__ import annotations

from . import demo_data as dd
from .openmetadata_client import OpenMetadataClient, OpenMetadataError


def _get_or_create(client: OpenMetadataClient, entity: str, name: str, creator, **kwargs):
    """Return existing entity or create it."""
    existing = client.get_by_name(entity, name)
    if existing:
        return existing
    return creator(name=name, **kwargs)


def ingest(client: OpenMetadataClient) -> dict:
    """Create all demo entities in OpenMetadata. Returns a summary dict."""
    created: dict[str, int] = {}

    # 1. Domains
    for name, _display, desc in dd.DOMAINS:
        if not client.exists("domains", name):
            client.create_domain(name, desc)
            created["domains"] = created.get("domains", 0) + 1

    # 2. Teams
    for name in dd.TEAMS:
        if not client.exists("teams", name):
            client.create_team(name)
            created["teams"] = created.get("teams", 0) + 1

    # 3. Classification + tags
    cls_name, cls_desc = dd.SENSITIVE_CLASSIFICATION
    if not client.exists("classifications", cls_name):
        client.create_classification(cls_name, cls_desc)
        created["classifications"] = created.get("classifications", 0) + 1
    for tag in dd.SENSITIVE_TAGS:
        tag_fqn = f"{cls_name}.{tag}"
        if not client.exists("tags", tag_fqn):
            client.create_tag(tag, cls_name)
            created["tags"] = created.get("tags", 0) + 1

    # 4. Glossary + terms
    glossary = "Business Glossary"
    if not client.exists("glossaries", glossary):
        client.create_glossary(glossary, "Business glossary for the demo.")
        created["glossaries"] = created.get("glossaries", 0) + 1
    for name, definition in dd.GLOSSARY:
        term_fqn = f"{glossary}.{name}"
        if not client.exists("glossaryTerms", term_fqn):
            client.create_glossary_term(name, glossary, definition)
            created["glossary_terms"] = created.get("glossary_terms", 0) + 1

    # 5. Database service → database → schemas
    if not client.exists("services/databaseServices", dd.DATABASE_SERVICE):
        client.create_database_service(dd.DATABASE_SERVICE, "Snowflake")
        created["services"] = created.get("services", 0) + 1
    db_fqn = f"{dd.DATABASE_SERVICE}.{dd.DATABASE}"
    if not client.exists("databases", db_fqn):
        client.create_database(dd.DATABASE, dd.DATABASE_SERVICE)
        created["databases"] = created.get("databases", 0) + 1
    for schema in dd.SCHEMAS:
        schema_fqn = f"{db_fqn}.{schema}"
        if not client.exists("databaseSchemas", schema_fqn):
            client.create_schema(schema, db_fqn)
            created["schemas"] = created.get("schemas", 0) + 1

    # 6. Tables + columns
    for spec in dd.CATALOG:
        schema_fqn = f"{db_fqn}.{spec['schema_name']}"
        table_fqn = f"{schema_fqn}.{spec['name']}"
        if client.exists("tables", table_fqn):
            continue
        columns = [
            dd.column_payload(n, t, desc, cls) for n, t, desc, cls in spec["columns"]
        ]
        try:
            client.create_table(
                name=spec["name"],
                schema_fqn=schema_fqn,
                description=spec["description"],
                owners=[spec["owner"]] if spec["owner"] else None,
                domains=[spec["domain"]] if spec["domain"] else None,
                columns=columns,
            )
            created["tables"] = created.get("tables", 0) + 1
        except OpenMetadataError as e:
            raise OpenMetadataError(f"Failed to create table {table_fqn}: {e}") from e

    return created
