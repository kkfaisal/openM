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

## Production features

### Connecting OpenMetadata (Metadata Tools)

1. **Connect a tool** → OpenMetadata → server URL + a **bot token**
   (Settings → Bots → ingestion-bot in OpenMetadata; recommended) or email/password.
2. **Test connection**: the steward calls `/system/version` and an authenticated
   endpoint. Saving is only possible after a successful test. Credentials are
   encrypted at rest with `METALENS_SECRET_KEY` and never returned by the API.
3. **Choose datasets**: browse services → databases (→ schemas, with table
   counts) live from OpenMetadata, tick what MetaLens should steward, optionally
   limit to some schemas and give a display name.
4. **Import**: each database becomes a dataset (`service.database`), is synced
   (cursor-paged, so large catalogs work) and scanned for gaps.

Each dataset can be re-synced, re-scoped or removed (OpenMetadata is never
modified by removal). Every scan syncs all imported datasets; a failing
connection is reported on its card and never blocks other connections.
Approved changes are written to the OpenMetadata instance that owns the table.

### RAG knowledge base

Everything ingested (Slack/Teams messages, spreadsheet rows, meeting
transcripts, JSON) plus every extracted fact is chunked, embedded and stored in
**Qdrant** with provenance (dataset, source, author, time, mentioned catalog
entities). Embeddings run locally with **fastembed** (`BAAI/bge-small-en-v1.5`,
no API key), or OpenAI via `EMBEDDING_PROVIDER=openai`.

* Agents retrieve passages about the table/column they work on; passages are
  added to the prompt (clearly marked as untrusted content) and attached to the
  recommendation as `RAG_PASSAGE` evidence with their similarity score.
* **Knowledge Base** page: *Ask* (grounded answers with clickable citations),
  *Search* (semantic search with a similarity floor) and *Browse* (every chunk),
  filterable by dataset, source, passages/facts and mentioned entity.
* `POST /api/rag/reindex` rebuilds the index (needed after changing the
  embedding model; the collection name includes the model so vectors never mix).

### Agent evaluation & monitoring (MLflow)

* **Tracing**: each investigation is an MLflow trace: an `AGENT` span with
  `RETRIEVER` (RAG) and `CHAT_MODEL` (prompt, output, token usage) children,
  tagged with agent, finding, entity and dataset.
* **Human feedback**: approve / edit / reject in the inbox is logged on the
  trace as `human_accepted` / `human_edited` assessments.
* **Evaluations** (`Agent Quality` page, or CLI):
  * `golden`: column descriptions and classifications against a labelled data
    dictionary, run **with and without RAG** to measure the lift (the golden
    file's own source is excluded from retrieval to avoid leakage);
  * `decisions`: acceptance/edit rates per field and confidence calibration
    (Brier score, expected calibration error) from real reviewer decisions.

  ```bash
  python -m app.evals --suite golden --limit 20 --min-description-similarity 0.6   # CI gate
  ```
* **Agent Quality** page: failure rate, latency p50/p95, acceptance and edit
  rates, calibration table, daily decisions, evaluation history and trace links.
  Live metrics come from the steward DB, so they work even when MLflow is down.

Local MLflow for development:

```bash
cd backend
mlflow server --port 5050 --backend-store-uri sqlite:///data/mlflow/mlflow.db --artifacts-destination ./data/mlflow/artifacts
# backend/.env
MLFLOW_TRACKING_URI=http://127.0.0.1:5050
```

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
export METALENS_SECRET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
docker compose up --build
```

- Frontend: <http://localhost:8080>
- Backend:  <http://localhost:8001/docs>
- MLflow:   <http://localhost:5000>
- Qdrant:   <http://localhost:6333/dashboard>

The stack runs the steward on PostgreSQL with Qdrant and an MLflow server.
Then open **Metadata Tools → Connect a tool** to add your OpenMetadata.

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
