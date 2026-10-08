# MetaLens

An agentic metadata management layer around **OpenMetadata** that continuously
observes, investigates, recommends, and — with human oversight — improves
enterprise metadata. OpenMetadata remains the system of record; this platform
stores only the steward's own state (findings, recommendations, evidence,
approvals, policies, audit history).

This repository is the **MVP vertical slice** described in `../reuirement.md`:

```
Catalog (OpenMetadata / demo)
   → Detect (deterministic rules)
   → Finding
   → Agent investigation
   → Evidence
   → Recommendation
   → Confidence engine
   → Policy engine
   → Human approval / safe automation
   → Apply to catalog
   → Audit
```

**The LLM recommends. The platform controls.**

---

## What's implemented (MVP)

- **Catalog abstraction** — typed read/write helpers over the metadata system
  of record. **OpenMetadata is the default backend** (real reads and writes
  against a live OpenMetadata instance); a `demo` backend seeds the same data
  into a local SQLite catalog for offline use.
- **Read-only scanner + finding engine** — deterministic detection of missing
  descriptions, missing column descriptions, missing owners, missing domains,
  missing sensitive-column classifications, and stale tables (no duplicates).
- **Agents** — Description, Ownership, Classification, and Staleness agents,
  each gathering verifiable evidence and producing a recommendation.
- **Evidence model** — every recommendation carries typed, verifiable evidence.
- **Confidence engine** — combines agent semantic score with evidence quality,
  normalized to 0–1 (never a bare LLM number).
- **Policy engine** — deterministic, database-backed, first-match-wins rules.
  Sensitive classifications and ownership always require approval by default.
- **Human-in-the-loop** — approval inbox with Approve / Reject / Modify /
  comment.
- **Apply + audit** — verified catalog writes with rollback value stored; full
  audit trail.
- **Health engine** — weighted coverage dimensions and overall score with
  snapshots for trend.
- **Web UI** — light-blue themed React app: Overview, Metadata Health,
  Findings, Recommendations, Approvals, Agent Runs, Changes, Policies,
  Activity, Catalog, Data Sources, and Settings.
- **Metadata sources** — connect Slack, Teams, CSV, Excel and JSON channels
  under a dataset (via file upload or Slack/Teams API), ingest the raw content,
  AI-extract and summarize relevant metadata (visible in the UI), and feed the
  extracted facts back in as evidence for the Description and Classification
  agents.

---

## Tech stack

| Layer     | Choice                                  |
|-----------|------------------------------------------|
| Backend   | Python 3.12+, FastAPI, Pydantic, SQLAlchemy |
| Database  | SQLite (steward snapshot; swap to PostgreSQL via `DATABASE_URL`) |
| Catalog   | **OpenMetadata 2.x REST API** (or local demo) |
| Frontend  | React 18 + TypeScript + Vite + Recharts  |
| LLM       | Pluggable: heuristic (default) or OpenAI |

---

## Local startup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

On first start the Steward creates a real PostgreSQL ecommerce database
(8 tables + sample rows in the `om-source-postgres` container), mirrors its
schema into OpenMetadata under a live `Postgres` service, syncs it locally, and
runs detection. Interactive API docs: <http://127.0.0.1:8001/docs>.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The Vite dev server proxies `/api` to the
backend on port **8001**.

> **Port note:** the backend runs on **8001** (not 8000) to avoid a common
> Docker/OpenMetadata port conflict. Change it in `backend` startup command and
> `frontend/vite.config.ts` together if needed.

### 3. Try the workflow

1. On **Overview**, click **Run scan** (or `POST /api/scans`).
2. Open **Findings** → click a finding → **Investigate** to run its agent.
3. Open **Approvals** and **Approve** / **Modify** / **Reject** a
   recommendation.
4. Watch the change appear under **Changes**, **Activity**, and the catalog
   update under **Catalog**.

---

## Docker

```bash
docker compose up --build
```

- Frontend: <http://localhost:8080>
- Backend:  <http://localhost:8001/docs>

---

## Configuration

Copy `.env.example` to `.env` and adjust. Key variables:

| Variable             | Purpose                                              |
|----------------------|------------------------------------------------------|
| `CATALOG_BACKEND`    | `openmetadata` (default) or `demo`                   |
| `OPENMETADATA_HOST`  | OpenMetadata URL (default `http://127.0.0.1:8585`)   |
| `OPENMETADATA_EMAIL` | Login email (default `admin@open-metadata.org`)      |
| `OPENMETADATA_PASSWORD` | Login password (default `admin`)                 |
| `OPENMETADATA_JWT`   | Optional long-lived bot token (overrides login)      |
| `LLM_PROVIDER`       | `heuristic` (no key) or `openai`                     |
| `OPENAI_API_KEY`     | OpenAI key (when `openai`)                           |
| `DATABASE_URL`       | SQLAlchemy URL (SQLite by default)                   |
| `POSTGRES_CONTAINER` | Source Postgres container (default `om-source-postgres`) |
| `POSTGRES_DB`        | Source database name (default `ecommerce`)           |
| `POSTGRES_HOST_PORT` | How OpenMetadata reaches the source Postgres         |

---

## OpenMetadata integration

The Steward talks to a **real OpenMetadata instance** as its system of record,
backed by a **real PostgreSQL ecommerce database**:

1. **Source database** — on first start it creates a real Postgres database
   `ecommerce` (8 tables: customers, products, orders, order_items, payments,
   inventory, reviews, categories) with sample rows in the `om-source-postgres`
   container.
2. **Mirror into OpenMetadata** — it creates a live `Postgres` database service
   in OpenMetadata with a real connection, then mirrors the schema (tables and
   columns) into OpenMetadata.
3. **Sync** — it pulls tables/columns/owners/domains from OpenMetadata into a
   local snapshot that the agents and health engine read.
4. **Detect → Recommend → Approve → Apply** — findings are generated from the
   real catalog; approving a recommendation **patches OpenMetadata directly**
   (description, owner, domain, and column classification tags) and records a
   verifiable change + audit event.

> Note: OpenMetadata 2.x serves column-tag reads through an eventually
> consistent path, so a freshly applied column classification can take a few
> seconds to appear in list/name lookups (it persists immediately).

### Reset the demo

To remove the steward's entities from OpenMetadata and start clean (the source
Postgres database is left intact):

```bash
cd backend
source .venv/bin/activate
python reset_openmetadata.py
rm -f metadata_steward.db
```

---

## Metadata sources (channels)

The steward can collect unstructured and structured metadata from many
channels and tie it to a dataset (`service.database`):

- **Upload** — CSV, Excel (`.xlsx`), JSON, a Slack export (JSON or ZIP), or a
  Teams export JSON.
- **API** — connect a Slack channel (bot token + channel id) or a Teams chat
  (Graph token + team/channel id) to pull messages live.

Slack/Teams API sources are **incremental (CDC)** and **schedulable**: a stored
cursor/watermark means each sync downloads only messages newer than the last
run, and a background scheduler (configurable interval) keeps them in sync
automatically. A "Sync now" button triggers an immediate incremental pull.

Flow: **connect source → ingest raw documents → AI extraction → visible
summary + facts → evidence for description/classification agents**. The
extracted facts (with their categories, target entity and confidence) are
shown in the **Data Sources** UI and attached to agent recommendations as
`SOURCE_EXTRACT` evidence, so every derived description/classification remains
traceable and still routes through the confidence + policy + approval
pipeline.

---

## API surface (subset)

```
GET  /api/overview
GET  /api/health            GET /api/health/history
GET  /api/findings          GET /api/findings/{id}
POST /api/findings/{id}/investigate
GET  /api/recommendations   GET /api/recommendations/{id}
POST /api/recommendations/{id}/approve | reject | modify
GET  /api/agent-runs        GET /api/agent-runs/{id}
GET  /api/changes
GET  /api/policies          POST /api/policies      PUT /api/policies/{id}
GET  /api/audit
POST /api/scans
GET  /api/catalog/tables    GET /api/catalog/domains
GET  /api/datasets/{key}/sources
POST /api/datasets/{key}/sources/upload      (multipart file)
POST /api/datasets/{key}/sources             (Slack/Teams API connect)
GET  /api/sources/{id}
GET  /api/sources/{id}/documents             GET /api/sources/{id}/facts
POST /api/sources/{id}/extract               DELETE /api/sources/{id}
POST /api/sources/{id}/sync                  PUT /api/sources/{id}/schedule
GET  /api/settings
```

OpenAPI documentation is generated automatically at `/docs`.

---

## Repository layout

```
backend/
  app/
    api/          # FastAPI routers
    services/     # scanner, findings, agents, confidence, policy, apply, ...
    models.py     # SQLAlchemy models (catalog + steward state)
    schemas.py    # Pydantic schemas
    seed.py       # demo catalog + policies + history
    main.py       # app entrypoint
frontend/
  src/
    pages/        # Overview, Findings, Approvals, ...
    components/   # Layout, RecommendationCard, ui
    lib/          # api client, formatting, hooks
infra/ (docker-compose.yml, Dockerfiles, nginx)
```

Agent logic, OpenMetadata integration, and business policies are kept
separate, per the spec's engineering rule.

---

## Security & guardrails (in place)

- Deterministic checks run **before** any LLM reasoning.
- Agents never receive raw catalog write access; writes go through typed
  services and the policy engine.
- Sensitive classification and ownership require approval by default.
- Metadata from the catalog is treated as untrusted content, never as
  instructions.
- No secrets in source; everything via environment variables.
- Every write is audited with previous/new value and rollback value.
