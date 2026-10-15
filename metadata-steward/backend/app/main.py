"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    agents,
    audit,
    catalog,
    changes,
    datasets,
    findings,
    health,
    llm,
    overview,
    policies,
    quality,
    rag,
    recommendations,
    scans,
    settings as settings_router,
    sources,
    tools,
)
from .config import settings
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .services import scheduler

    scheduler.start()
    yield
    from .services import rag

    rag.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Agentic metadata management layer around OpenMetadata — observe, "
        "investigate, recommend, approve and audit metadata improvements."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    overview.router,
    health.router,
    findings.router,
    recommendations.router,
    agents.router,
    changes.router,
    policies.router,
    audit.router,
    scans.router,
    catalog.router,
    datasets.router,
    sources.router,
    tools.router,
    llm.router,
    rag.router,
    quality.router,
    settings_router.router,
):
    app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "catalog_backend": settings.catalog_backend,
    }


@app.get("/api/ping")
def ping() -> dict:
    return {"status": "ok"}
