"""Real PostgreSQL ecommerce source.

Creates an actual PostgreSQL database (tables + data) in the `om-source-postgres`
container, then mirrors that schema into OpenMetadata as a *real* Postgres
database service with a live connection config.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .openmetadata_client import OpenMetadataClient

POSTGRES_CONTAINER = os.getenv("POSTGRES_CONTAINER", "om-source-postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "omdev")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ecommerce")
# How OpenMetadata (inside Docker) reaches the source Postgres.
POSTGRES_HOST_PORT = os.getenv("POSTGRES_HOST_PORT", "host.docker.internal:55432")

SERVICE_NAME = "ecommerce_postgres"

TEAMS = [
    "Ecommerce Data Engineering",
    "Sales Analytics",
    "Payments Platform",
    "Catalog Operations",
]

DOMAINS = [
    ("Sales", "Sales", "Sales orders and revenue data."),
    ("Customer", "Customer", "Customer master data."),
    ("Catalog", "Catalog", "Products and categories."),
    ("Payments", "Payments", "Payment processing data."),
    ("Fulfillment", "Fulfillment", "Inventory and fulfillment data."),
]

# Every tag the classification agent can recommend must exist in OpenMetadata,
# otherwise applying a classification fails with "Entity not found: tag ...".
SENSITIVE_TAGS = [
    "CustomerIdentifier",
    "PaymentCard",
    "Email",
    "PhoneNumber",
    "Address",
    "SSN",
    "DateOfBirth",
    "Credential",
    "IPAddress",
    "PersonalFinancial",
    "Name",
    "PersonalData",
]

# Tables (name, description, domain, owner, [columns]).
# Columns: (name, data_type, description, classification)
# Deliberate gaps (None description/owner/domain/classification) mirror the SQL
# comments so the steward detects real documentation issues.
TABLES: list[dict] = [
    {
        "name": "customers",
        "description": "Registered customers of the ecommerce store.",
        "domain": "Customer",
        "owner": "Ecommerce Data Engineering",
        "columns": [
            ("customer_id", "INTEGER", "Unique customer identifier.", None),
            ("first_name", "VARCHAR", "Customer first name.", None),
            ("last_name", "VARCHAR", "Customer last name.", None),
            ("email", "VARCHAR", "Customer email address (unique).", "Sensitive.Email"),
            ("phone", "VARCHAR", None, "Sensitive.PhoneNumber"),
            ("address_line1", "VARCHAR", None, "Sensitive.Address"),
            ("city", "VARCHAR", None, None),
            ("country", "VARCHAR", None, None),
            ("postal_code", "VARCHAR", None, None),
            ("created_at", "TIMESTAMP", "Timestamp the customer record was created.", None),
        ],
    },
    {
        "name": "categories",
        "description": "Product categories used for catalog organisation.",
        "domain": "Catalog",
        "owner": "Catalog Operations",
        "columns": [
            ("category_id", "INTEGER", "Unique category identifier.", None),
            ("name", "VARCHAR", "Category display name.", None),
            ("description", "TEXT", None, None),
        ],
    },
    {
        "name": "products",
        "description": "Products available for sale in the storefront.",
        "domain": "Catalog",
        "owner": "Catalog Operations",
        "columns": [
            ("product_id", "INTEGER", "Unique product identifier.", None),
            ("category_id", "INTEGER", None, None),
            ("sku", "VARCHAR", "Stock keeping unit (SKU) code.", None),
            ("name", "VARCHAR", "Product display name.", None),
            ("description", "TEXT", None, None),
            ("price", "NUMERIC", "Unit price in the configured currency.", None),
            ("currency", "VARCHAR", None, None),
            ("stock_quantity", "INTEGER", None, None),
            ("is_active", "BOOLEAN", None, None),
            ("created_at", "TIMESTAMP", None, None),
        ],
    },
    {
        "name": "orders",
        "description": "Customer orders placed in the store.",
        "domain": "Sales",
        "owner": "Sales Analytics",
        "columns": [
            ("order_id", "INTEGER", "Unique order identifier.", None),
            ("customer_id", "INTEGER", "Customer that placed the order.", None),
            ("order_date", "TIMESTAMP", None, None),
            ("status", "VARCHAR", "Order lifecycle status.", None),
            ("subtotal", "NUMERIC", None, None),
            ("tax", "NUMERIC", None, None),
            ("shipping", "NUMERIC", None, None),
            ("total_amount", "NUMERIC", None, None),
            ("shipping_address", "TEXT", None, "Sensitive.Address"),
            ("created_at", "TIMESTAMP", None, None),
        ],
    },
    {
        "name": "order_items",
        "description": "Line items that belong to an order.",
        "domain": "Sales",
        "owner": "Sales Analytics",
        "columns": [
            ("order_item_id", "INTEGER", "Unique line item identifier.", None),
            ("order_id", "INTEGER", None, None),
            ("product_id", "INTEGER", None, None),
            ("quantity", "INTEGER", None, None),
            ("unit_price", "NUMERIC", None, None),
            ("discount", "NUMERIC", None, None),
        ],
    },
    {
        "name": "payments",
        "description": None,  # gap: missing description
        "domain": "Payments",
        "owner": "Payments Platform",
        "columns": [
            ("payment_id", "INTEGER", None, None),
            ("order_id", "INTEGER", None, None),
            ("payment_method", "VARCHAR", None, None),
            ("amount", "NUMERIC", None, None),
            ("currency", "VARCHAR", None, None),
            ("card_number", "VARCHAR", None, None),  # gap: sensitive + unclassified
            ("status", "VARCHAR", None, None),
            ("paid_at", "TIMESTAMP", None, None),
        ],
    },
    {
        "name": "inventory",
        "description": None,  # gap: missing description
        "domain": "Fulfillment",
        "owner": "Catalog Operations",
        "columns": [
            ("inventory_id", "INTEGER", None, None),
            ("product_id", "INTEGER", None, None),
            ("warehouse_code", "VARCHAR", None, None),
            ("quantity_on_hand", "INTEGER", None, None),
            ("reorder_level", "INTEGER", None, None),
            ("updated_at", "TIMESTAMP", None, None),
        ],
    },
    {
        "name": "reviews",
        "description": None,  # gap: missing description
        "domain": None,       # gap: missing domain
        "owner": None,        # gap: missing owner
        "columns": [
            ("review_id", "INTEGER", None, None),
            ("product_id", "INTEGER", None, None),
            ("customer_id", "INTEGER", None, None),
            ("rating", "INTEGER", None, None),
            ("comment", "TEXT", None, None),
            ("created_at", "TIMESTAMP", None, None),
        ],
    },
]

DATA_TYPE_MAP = {
    "INTEGER": "INT",
    "VARCHAR": "VARCHAR",
    "TEXT": "TEXT",
    "NUMERIC": "DECIMAL",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "BOOLEAN",
}


def _sql_file() -> Path:
    return Path(__file__).parent / "ecommerce.sql"


def _run_psql(sql: str, database: str | None = None) -> str:
    cmd = ["docker", "exec", "-i", POSTGRES_CONTAINER, "psql", "-U", POSTGRES_USER]
    if database:
        cmd += ["-d", database]
    cmd += ["-v", "ON_ERROR_STOP=1", "-q"]
    proc = subprocess.run(cmd, input=sql, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def ensure_postgres_database() -> None:
    """Create the ecommerce database (if absent) and apply the schema + seed.

    Idempotent: skips the schema/seed if it has already been applied.
    """
    exists = _run_psql(
        f"SELECT 1 FROM pg_database WHERE datname = '{POSTGRES_DB}'"
    )
    if "1" not in exists:
        _run_psql(f'CREATE DATABASE "{POSTGRES_DB}"')

    # If the schema is already present, don't re-apply (re-inserting would
    # duplicate rows / violate unique constraints).
    already = _run_psql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'customers'",
        database=POSTGRES_DB,
    )
    if "1" in already:
        return

    _run_psql(_sql_file().read_text(), database=POSTGRES_DB)


def ingest(client: OpenMetadataClient) -> dict:
    """Mirror the ecommerce schema into OpenMetadata under a real Postgres
    service. Idempotent."""
    created: dict[str, int] = {}

    # Teams + domains
    for name in TEAMS:
        if not client.exists("teams", name):
            client.create_team(name)
            created["teams"] = created.get("teams", 0) + 1
    for name, _display, desc in DOMAINS:
        if not client.exists("domains", name):
            client.create_domain(name, desc)
            created["domains"] = created.get("domains", 0) + 1

    # Sensitive classification + tags
    if not client.exists("classifications", "Sensitive"):
        client.create_classification("Sensitive", "Sensitive or personal data.")
        created["classifications"] = 1
    for tag in SENSITIVE_TAGS:
        if not client.exists("tags", f"Sensitive.{tag}"):
            client.create_tag(tag, "Sensitive")
            created["tags"] = created.get("tags", 0) + 1

    # Postgres service (real connection) + database + schema
    if not client.exists("services/databaseServices", SERVICE_NAME):
        client.create_postgres_service(
            SERVICE_NAME,
            host_port=POSTGRES_HOST_PORT,
            username=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
        )
        created["services"] = 1
    db_fqn = f"{SERVICE_NAME}.{POSTGRES_DB}"
    if not client.exists("databases", db_fqn):
        client.create_database(POSTGRES_DB, SERVICE_NAME)
        created["databases"] = 1
    schema_fqn = f"{db_fqn}.public"
    if not client.exists("databaseSchemas", schema_fqn):
        client.create_schema("public", db_fqn)
        created["schemas"] = 1

    # Tables + columns
    for spec in TABLES:
        table_fqn = f"{schema_fqn}.{spec['name']}"
        if client.exists("tables", table_fqn):
            continue
        columns = [
            _column_payload(n, t, d, c) for n, t, d, c in spec["columns"]
        ]
        client.create_table(
            name=spec["name"],
            schema_fqn=schema_fqn,
            description=spec["description"],
            owners=[spec["owner"]] if spec["owner"] else None,
            domains=[spec["domain"]] if spec["domain"] else None,
            columns=columns,
        )
        created["tables"] = created.get("tables", 0) + 1

    return created


def _column_payload(name: str, data_type: str, description: str | None, classification: str | None) -> dict:
    dt = DATA_TYPE_MAP.get(data_type, data_type)
    payload: dict = {"name": name, "dataType": dt, "dataTypeDisplay": data_type.lower()}
    if dt == "DECIMAL":
        payload["precision"] = 18
        payload["scale"] = 2
    elif dt in ("VARCHAR", "TEXT", "CHAR"):
        payload["dataLength"] = 255
    if description:
        payload["description"] = description
    if classification:
        payload["tags"] = [{"tagFQN": classification}]
    return payload
