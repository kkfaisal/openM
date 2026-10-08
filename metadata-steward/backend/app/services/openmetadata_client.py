"""OpenMetadata 2.x REST client.

A thin, typed wrapper over the OpenMetadata API. The steward never makes raw
HTTP calls from agent code — it goes through this client. Authentication uses
the login endpoint (JWT) and refreshes lazily on expiry/401.
"""
from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from ..config import settings


class OpenMetadataError(RuntimeError):
    pass


class OpenMetadataClient:
    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.openmetadata_host or "").rstrip("/")
        if not self.base_url:
            raise OpenMetadataError("OPENMETADATA_HOST is not configured.")
        self.email = email or settings.openmetadata_email or "admin@open-metadata.org"
        self.password = password or settings.openmetadata_password or "admin"
        self._token: str | None = None
        self._expiry: float = 0.0

    # -- auth -------------------------------------------------------------- #
    def _login(self) -> str:
        encoded = base64.b64encode(self.password.encode()).decode()
        resp = httpx.post(
            f"{self.base_url}/api/v1/users/login",
            json={"email": self.email, "password": encoded},
            timeout=30,
        )
        data = self._check(resp)
        token = data.get("accessToken")
        if not token:
            raise OpenMetadataError("Login did not return an access token.")
        self._token = token
        # JWT exp is in seconds; fall back to 1h if unavailable.
        self._expiry = time.time() + 3000
        return token

    def _ensure_token(self) -> str:
        if not self._token or time.time() > self._expiry - 60:
            return self._login()
        return self._token

    def _check(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                body = resp.text
            raise OpenMetadataError(
                f"OpenMetadata {resp.status_code}: {body}"
            )
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict | None = None,
        retry: bool = True,
    ) -> Any:
        token = self._ensure_token()
        url = f"{self.base_url}{path}"
        content_type = (
            "application/json-patch+json"
            if method.upper() == "PATCH"
            else "application/json"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        }
        try:
            resp = httpx.request(
                method, url, headers=headers, json=json, params=params, timeout=60
            )
        except httpx.HTTPError as e:
            raise OpenMetadataError(str(e)) from e

        if resp.status_code == 401 and retry:
            # Token expired — re-login once and retry.
            self._login()
            return self._request(method, path, json=json, params=params, retry=False)
        return self._check(resp)

    # -- generic helpers --------------------------------------------------- #
    def list_all(self, entity: str, params: dict | None = None) -> list[dict]:
        params = dict(params or {})
        params.setdefault("limit", 1000)
        data = self._request("GET", f"/api/v1/{entity}", params=params)
        return data.get("data", []) if isinstance(data, dict) else data

    def get_by_name(self, entity: str, fqn: str) -> dict | None:
        try:
            return self._request("GET", f"/api/v1/{entity}/name/{fqn}")
        except OpenMetadataError:
            return None

    def delete(self, entity: str, entity_id: str, *, hard: bool = True) -> dict:
        return self._request(
            "DELETE",
            f"/api/v1/{entity}/{entity_id}",
            params={"hardDelete": "true" if hard else "false"},
        )

    def exists(self, entity: str, fqn: str) -> bool:
        return self.get_by_name(entity, fqn) is not None

    # -- read entities ----------------------------------------------------- #
    def list_tables(self) -> list[dict]:
        return self.list_all(
            "tables", params={"fields": "columns,owners,domains,tags,databaseSchema"}
        )

    def list_domains(self) -> list[dict]:
        return self.list_all("domains")

    def list_teams(self) -> list[dict]:
        return self.list_all("teams")

    def list_glossary_terms(self) -> list[dict]:
        return self.list_all("glossaryTerms")

    def list_tags(self) -> list[dict]:
        return self.list_all("tags")

    # -- create entities --------------------------------------------------- #
    def create_domain(self, name: str, description: str = "") -> dict:
        return self._request(
            "POST",
            "/api/v1/domains",
            json={"name": name, "domainType": "Aggregate", "description": description},
        )

    def create_team(self, name: str) -> dict:
        return self._request(
            "POST", "/api/v1/teams", json={"name": name, "teamType": "Group"}
        )

    def create_classification(self, name: str, description: str = "") -> dict:
        return self._request(
            "POST",
            "/api/v1/classifications",
            json={"name": name, "description": description},
        )

    def create_tag(self, name: str, classification: str, description: str = "") -> dict:
        return self._request(
            "POST",
            "/api/v1/tags",
            json={
                "name": name,
                "classification": classification,
                "description": description or name,
            },
        )

    def create_glossary(self, name: str, description: str = "") -> dict:
        return self._request(
            "POST", "/api/v1/glossaries", json={"name": name, "description": description}
        )

    def create_glossary_term(
        self, name: str, glossary: str, description: str = ""
    ) -> dict:
        return self._request(
            "POST",
            "/api/v1/glossaryTerms",
            json={
                "name": name,
                "glossary": glossary,
                "description": description or name,
            },
        )

    def create_database_service(self, name: str, service_type: str = "Snowflake") -> dict:
        return self._request(
            "POST",
            "/api/v1/services/databaseServices",
            json={
                "name": name,
                "serviceType": service_type,
                "connection": {
                    "config": {
                        "type": service_type,
                        "username": "dummy",
                        "password": "dummy",
                        "account": "dummy",
                        "warehouse": "dummy",
                        "database": "dummy",
                    }
                },
            },
        )

    def create_postgres_service(
        self,
        name: str,
        *,
        host_port: str,
        username: str,
        password: str,
        database: str,
    ) -> dict:
        return self._request(
            "POST",
            "/api/v1/services/databaseServices",
            json={
                "name": name,
                "serviceType": "Postgres",
                "connection": {
                    "config": {
                        "type": "Postgres",
                        "scheme": "postgresql+psycopg2",
                        "username": username,
                        "authType": {"password": password},
                        "hostPort": host_port,
                        "database": database,
                    }
                },
            },
        )

    def create_database(self, name: str, service: str) -> dict:
        return self._request(
            "POST", "/api/v1/databases", json={"name": name, "service": service}
        )

    def create_schema(self, name: str, database: str) -> dict:
        return self._request(
            "POST", "/api/v1/databaseSchemas", json={"name": name, "database": database}
        )

    def create_table(
        self,
        *,
        name: str,
        schema_fqn: str,
        description: str | None = None,
        owners: list[str] | None = None,
        domains: list[str] | None = None,
        columns: list[dict] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"name": name, "databaseSchema": schema_fqn}
        if description:
            payload["description"] = description
        if columns:
            payload["columns"] = columns
        table = self._request("POST", "/api/v1/tables", json=payload)

        # Owners/domains are set via patch (arrays in 2.x).
        if owners or domains:
            patches: list[dict] = []
            for i, owner in enumerate(owners or []):
                owner_id = self._team_id_by_name(owner)
                if owner_id:
                    patches.append(
                        {"op": "add", "path": f"/owners/{i}", "value": {"id": owner_id, "type": "team"}}
                    )
            for i, dom in enumerate(domains or []):
                dom_id = self._domain_id_by_name(dom)
                if dom_id:
                    patches.append(
                        {"op": "add", "path": f"/domains/{i}", "value": {"id": dom_id, "type": "domain"}}
                    )
            if patches:
                self.patch_table(table["id"], patches)
                table = self.get_by_name("tables", table["fullyQualifiedName"]) or table
        return table

    # -- id helpers -------------------------------------------------------- #
    def _team_id_by_name(self, name: str) -> str | None:
        t = self.get_by_name("teams", name)
        return t.get("id") if t else None

    def _domain_id_by_name(self, name: str) -> str | None:
        d = self.get_by_name("domains", name)
        return d.get("id") if d else None

    def _table_id_by_fqn(self, fqn: str) -> str | None:
        t = self.get_by_name("tables", fqn)
        return t.get("id") if t else None

    # -- patch ------------------------------------------------------------- #
    def patch_table(self, table_id: str, patches: list[dict]) -> dict:
        return self._request(
            "PATCH",
            f"/api/v1/tables/{table_id}",
            json=patches,
        )

    def update_table_description(self, fqn: str, value: str) -> None:
        table_id = self._table_id_by_fqn(fqn)
        if not table_id:
            raise OpenMetadataError(f"Table not found: {fqn}")
        self.patch_table(
            table_id, [{"op": "add", "path": "/description", "value": value}]
        )

    def update_table_owner(self, fqn: str, team_name: str) -> None:
        table_id = self._table_id_by_fqn(fqn)
        team_id = self._team_id_by_name(team_name)
        if not table_id or not team_id:
            raise OpenMetadataError(f"Unable to resolve table '{fqn}' or team '{team_name}'")

        # Idempotent: skip if this team is already the owner (avoiding the
        # OpenMetadata "Multiple Users or Single Team Ownership" rule violation
        # that a duplicate add would trigger).
        table = self.get_by_name("tables", fqn)
        current = [o.get("id") for o in (table.get("owners") or []) if o]
        if team_id in current:
            return

        self.patch_table(
            table_id,
            [{"op": "add", "path": "/owners/0", "value": {"id": team_id, "type": "team"}}],
        )

    def update_table_domain(self, fqn: str, domain_name: str) -> None:
        table_id = self._table_id_by_fqn(fqn)
        domain_id = self._domain_id_by_name(domain_name)
        if not table_id or not domain_id:
            raise OpenMetadataError(f"Unable to resolve table '{fqn}' or domain '{domain_name}'")
        self.patch_table(
            table_id,
            [{"op": "add", "path": "/domains/0", "value": {"id": domain_id, "type": "domain"}}],
        )

    def update_column_tag(self, table_fqn: str, column_name: str, tag_fqn: str) -> None:
        """Set a classification tag on a column by name."""
        table = self.get_by_name("tables", table_fqn)
        if not table:
            raise OpenMetadataError(f"Table not found: {table_fqn}")
        columns = table.get("columns") or []
        idx = next(
            (i for i, c in enumerate(columns) if c.get("name") == column_name), None
        )
        if idx is None:
            raise OpenMetadataError(f"Column not found: {table_fqn}.{column_name}")
        self.patch_table(
            table["id"],
            [{"op": "add", "path": f"/columns/{idx}/tags/0", "value": {"tagFQN": tag_fqn}}],
        )

    def update_column_description(
        self, table_fqn: str, column_name: str, value: str
    ) -> None:
        table = self.get_by_name("tables", table_fqn)
        if not table:
            raise OpenMetadataError(f"Table not found: {table_fqn}")
        columns = table.get("columns") or []
        idx = next(
            (i for i, c in enumerate(columns) if c.get("name") == column_name), None
        )
        if idx is None:
            raise OpenMetadataError(f"Column not found: {table_fqn}.{column_name}")
        self.patch_table(
            table["id"],
            [{"op": "add", "path": f"/columns/{idx}/description", "value": value}],
        )


_client: OpenMetadataClient | None = None


def get_client() -> OpenMetadataClient:
    """Lazily construct a shared client."""
    global _client
    if _client is None:
        _client = OpenMetadataClient()
    return _client


def reset_client() -> None:
    global _client
    _client = None
