"""Demo catalog data shared by the local demo seed and the OpenMetadata
ingestion. This is the *dummy input*; everything downstream (detection,
recommendation, approval, apply, audit) operates for real against whichever
catalog backend is configured.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _days_ago(days: int) -> datetime:
    return _now() - timedelta(days=days)


# Columns are (name, data_type, description, classification).
CATALOG: list[dict] = [
    # ---------------------------- Finance ---------------------------- #
    {
        "fqn": "finance.fact_payment",
        "name": "fact_payment",
        "schema_name": "finance",
        "domain": "Finance",
        "owner": "Finance Data Engineering",
        "description": (
            "Contains processed customer payment transactions used for "
            "financial reporting and revenue analytics."
        ),
        "row_count": 128_400_000,
        "last_queried_at": _days_ago(1),
        "columns": [
            ("payment_id", "VARCHAR", "Unique payment identifier", None),
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("payment_amount", "DECIMAL", "Payment amount in transaction currency", None),
            ("currency", "VARCHAR", "ISO currency code", None),
            ("payment_date", "DATE", "Date the payment was processed", None),
            ("card_hash", "VARCHAR", None, None),
            ("status", "VARCHAR", "Payment status", None),
            ("created_at", "TIMESTAMP", "Record creation timestamp", None),
        ],
    },
    {
        "fqn": "finance.dim_account",
        "name": "dim_account",
        "schema_name": "finance",
        "domain": "Finance",
        "owner": "Finance Data Engineering",
        "description": "Dimension of customer accounts with lifecycle attributes.",
        "row_count": 4_200_000,
        "last_queried_at": _days_ago(3),
        "columns": [
            ("account_id", "VARCHAR", "Account identifier", None),
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("account_type", "VARCHAR", "Account type", None),
            ("balance", "DECIMAL", "Current account balance", None),
            ("opened_at", "DATE", "Account opening date", None),
        ],
    },
    {
        "fqn": "finance.fact_revenue",
        "name": "fact_revenue",
        "schema_name": "finance",
        "domain": "Finance",
        "owner": None,
        "description": None,
        "row_count": 96_000_000,
        "last_queried_at": _days_ago(2),
        "columns": [
            ("revenue_id", "VARCHAR", "Revenue line identifier", None),
            ("account_id", "VARCHAR", "Account identifier", None),
            ("revenue_amount", "DECIMAL", "Recognized revenue amount", None),
            ("period", "DATE", "Reporting period", None),
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
        ],
    },
    {
        "fqn": "finance.ledger_entries",
        "name": "ledger_entries",
        "schema_name": "finance",
        "domain": "Finance",
        "owner": "Finance Data Engineering",
        "description": "General ledger journal entries for accounting.",
        "row_count": 210_000_000,
        "last_queried_at": _days_ago(210),
        "columns": [
            ("entry_id", "VARCHAR", "Journal entry identifier", None),
            ("account_id", "VARCHAR", "Account identifier", None),
            ("debit", "DECIMAL", "Debit amount", None),
            ("credit", "DECIMAL", "Credit amount", None),
            ("posted_at", "DATE", "Posting date", None),
        ],
    },
    # ---------------------------- Customer ---------------------------- #
    {
        "fqn": "customer.dim_customer",
        "name": "dim_customer",
        "schema_name": "customer",
        "domain": "Customer",
        "owner": "Customer Analytics",
        "description": "Master customer dimension with contact and segmentation attributes.",
        "row_count": 34_000_000,
        "last_queried_at": _days_ago(1),
        "columns": [
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("email", "VARCHAR", None, None),
            ("phone", "VARCHAR", None, None),
            ("full_name", "VARCHAR", "Customer full name", None),
            ("address", "VARCHAR", None, None),
            ("segment", "VARCHAR", "Customer segment", None),
            ("created_at", "TIMESTAMP", "Record creation timestamp", None),
        ],
    },
    {
        "fqn": "customer.customer_360",
        "name": "customer_360",
        "schema_name": "customer",
        "domain": "Customer",
        "owner": "Customer Analytics",
        "description": None,
        "row_count": 8_000_000,
        "last_queried_at": _days_ago(5),
        "columns": [
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("lifetime_value", "DECIMAL", "Customer lifetime value", None),
            ("order_count", "INTEGER", "Total orders", None),
            ("last_order_at", "DATE", "Most recent order date", None),
        ],
    },
    {
        "fqn": "customer.customer_churn",
        "name": "customer_churn",
        "schema_name": "customer",
        "domain": "Customer",
        "owner": None,
        "description": "Customer churn predictions with risk scores.",
        "row_count": 3_500_000,
        "last_queried_at": _days_ago(4),
        "columns": [
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("churn_risk", "FLOAT", "Predicted churn probability", None),
            ("prediction_date", "DATE", "Prediction date", None),
        ],
    },
    # ---------------------------- Orders ---------------------------- #
    {
        "fqn": "orders.fact_order",
        "name": "fact_order",
        "schema_name": "orders",
        "domain": "Orders",
        "owner": "Customer Analytics",
        "description": "Transactional order facts for fulfillment and revenue analysis.",
        "row_count": 76_000_000,
        "last_queried_at": _days_ago(1),
        "columns": [
            ("order_id", "VARCHAR", "Order identifier", None),
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("order_date", "DATE", "Order date", None),
            ("order_status", "VARCHAR", "Order status", None),
            ("total_value", "DECIMAL", "Total order value", None),
        ],
    },
    {
        "fqn": "orders.order_items",
        "name": "order_items",
        "schema_name": "orders",
        "domain": "Orders",
        "owner": "Customer Analytics",
        "description": None,
        "row_count": 210_000_000,
        "last_queried_at": _days_ago(2),
        "columns": [
            ("order_item_id", "VARCHAR", "Order item identifier", None),
            ("order_id", "VARCHAR", "Order identifier", None),
            ("product_id", "VARCHAR", "Product identifier", None),
            ("quantity", "INTEGER", "Quantity ordered", None),
            ("unit_price", "DECIMAL", "Unit price", None),
        ],
    },
    {
        "fqn": "orders.order_status_history",
        "name": "order_status_history",
        "schema_name": "orders",
        "domain": None,
        "owner": "Customer Analytics",
        "description": "Status transitions for orders over time.",
        "row_count": 88_000_000,
        "last_queried_at": _days_ago(150),
        "columns": [
            ("order_id", "VARCHAR", "Order identifier", None),
            ("from_status", "VARCHAR", "Previous status", None),
            ("to_status", "VARCHAR", "New status", None),
            ("changed_at", "TIMESTAMP", "Status change timestamp", None),
        ],
    },
    # ---------------------------- Payments ---------------------------- #
    {
        "fqn": "payments.payment_transactions",
        "name": "payment_transactions",
        "schema_name": "payments",
        "domain": "Payments",
        "owner": "Payments Platform",
        "description": "Raw payment transactions ingested from the payment gateway.",
        "row_count": 300_000_000,
        "last_queried_at": _days_ago(0),
        "columns": [
            ("payment_id", "VARCHAR", "Payment identifier", None),
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("card_hash", "VARCHAR", None, None),
            ("payment_amount", "DECIMAL", "Payment amount", None),
            ("currency", "VARCHAR", "ISO currency code", None),
            ("status", "VARCHAR", "Payment status", None),
            ("created_at", "TIMESTAMP", "Record creation timestamp", None),
        ],
    },
    {
        "fqn": "payments.refunds",
        "name": "refunds",
        "schema_name": "payments",
        "domain": "Payments",
        "owner": "Payments Platform",
        "description": "Refund records linked to original payment transactions.",
        "row_count": 12_000_000,
        "last_queried_at": _days_ago(6),
        "columns": [
            ("refund_id", "VARCHAR", "Refund identifier", None),
            ("payment_id", "VARCHAR", "Original payment identifier", None),
            ("refund_amount", "DECIMAL", "Refunded amount", None),
            ("reason", "VARCHAR", "Refund reason", None),
            ("created_at", "TIMESTAMP", "Record creation timestamp", None),
        ],
    },
    {
        "fqn": "payments.settlements",
        "name": "settlements",
        "schema_name": "payments",
        "domain": "Payments",
        "owner": None,
        "description": None,
        "row_count": 9_000_000,
        "last_queried_at": _days_ago(3),
        "columns": [
            ("settlement_id", "VARCHAR", "Settlement identifier", None),
            ("payout_id", "VARCHAR", "Payout identifier", None),
            ("amount", "DECIMAL", "Settlement amount", None),
            ("currency", "VARCHAR", "ISO currency code", None),
            ("settled_at", "DATE", "Settlement date", None),
        ],
    },
    # ---------------------------- Marketing ---------------------------- #
    {
        "fqn": "marketing.campaign_performance",
        "name": "campaign_performance",
        "schema_name": "marketing",
        "domain": "Marketing",
        "owner": "Marketing Analytics",
        "description": "Campaign-level performance metrics for marketing reporting.",
        "row_count": 1_800_000,
        "last_queried_at": _days_ago(2),
        "columns": [
            ("campaign_id", "VARCHAR", "Campaign identifier", None),
            ("impressions", "INTEGER", "Total impressions", None),
            ("clicks", "INTEGER", "Total clicks", None),
            ("conversions", "INTEGER", "Total conversions", None),
            ("spend", "DECIMAL", "Campaign spend", None),
        ],
    },
    {
        "fqn": "marketing.customer_segments",
        "name": "customer_segments",
        "schema_name": "marketing",
        "domain": "Marketing",
        "owner": "Marketing Analytics",
        "description": None,
        "row_count": 600_000,
        "last_queried_at": _days_ago(7),
        "columns": [
            ("segment_id", "VARCHAR", "Segment identifier", None),
            ("segment_name", "VARCHAR", "Segment name", None),
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("created_at", "TIMESTAMP", "Record creation timestamp", None),
        ],
    },
    {
        "fqn": "marketing.customer_campaign_v1",
        "name": "customer_campaign_v1",
        "schema_name": "marketing",
        "domain": "Marketing",
        "owner": "Marketing Analytics",
        "description": "Legacy campaign attribution table (superseded by v2).",
        "row_count": 2_200_000,
        "last_queried_at": _days_ago(180),
        "columns": [
            ("customer_id", "VARCHAR", "Customer identifier", "Sensitive.CustomerIdentifier"),
            ("campaign_id", "VARCHAR", "Campaign identifier", None),
            ("attributed_value", "DECIMAL", "Attributed value", None),
            ("attribution_date", "DATE", "Attribution date", None),
        ],
    },
]

DOMAINS = [
    ("Finance", "Finance", "Financial reporting and accounting data."),
    ("Customer", "Customer", "Customer master and relationship data."),
    ("Orders", "Orders", "Order and fulfillment data."),
    ("Payments", "Payments", "Payment processing and settlement data."),
    ("Marketing", "Marketing", "Campaign and marketing analytics data."),
]

TEAMS = [
    "Finance Data Engineering",
    "Customer Analytics",
    "Payments Platform",
    "Marketing Analytics",
    "Data Platform",
]

GLOSSARY = [
    ("Customer Identifier", "Unique identifier for a customer across systems."),
    ("Payment Transaction", "A processed payment between a customer and merchant."),
    ("Order", "A customer order for one or more products."),
    ("Revenue", "Recognized revenue for financial reporting."),
    ("Email Address", "Customer contact email address."),
    ("Campaign", "A marketing campaign."),
]

# Classification + tags created in OpenMetadata.
SENSITIVE_CLASSIFICATION = ("Sensitive", "Sensitive or personal data.")
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

DATABASE_SERVICE = "demo_snowflake"
DATABASE = "ANALYTICS"
SCHEMAS = ["finance", "customer", "orders", "payments", "marketing"]

# Map our friendly data types to OpenMetadata DataType enum values.
DATA_TYPE_MAP = {
    "VARCHAR": "VARCHAR",
    "DECIMAL": "DECIMAL",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "INTEGER": "INT",
    "FLOAT": "FLOAT",
}


def column_payload(name: str, data_type: str, description: str | None, classification: str | None) -> dict:
    """Build an OpenMetadata column payload (omits description/tags when gaps
    are intentional)."""
    dt = DATA_TYPE_MAP.get(data_type, data_type)
    payload: dict = {
        "name": name,
        "dataType": dt,
        "dataTypeDisplay": data_type.lower(),
    }
    if dt == "DECIMAL":
        payload["precision"] = 18
        payload["scale"] = 2
    elif dt in ("VARCHAR", "CHAR", "TEXT"):
        payload["dataLength"] = 255
    if description:
        payload["description"] = description
    if classification:
        payload["tags"] = [{"tagFQN": classification}]
    return payload
