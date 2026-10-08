"""Metadata-tool connection endpoints (OpenMetadata, Amundsen, DataHub, ...)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CatalogTable, Finding, MetadataTool
from ..schemas import MetadataToolOut, ToolCreate
from ..services import tools as tools_service

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _tool_out(db: Session, tool: MetadataTool) -> MetadataToolOut:
    count = (
        db.query(CatalogTable.service_name, CatalogTable.database_name)
        .filter(CatalogTable.tool_id == tool.id)
        .distinct()
        .count()
    )
    return MetadataToolOut(
        id=tool.id,
        name=tool.name,
        type=tool.type,
        host=tool.host,
        config=tool.config,
        status=tool.status,
        is_default=tool.is_default,
        dataset_count=count,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


@router.get("", response_model=list[MetadataToolOut])
def list_tools(db: Session = Depends(get_db)):
    tools = (
        db.query(MetadataTool)
        .order_by(MetadataTool.is_default.desc(), MetadataTool.name.asc())
        .all()
    )
    return [_tool_out(db, t) for t in tools]


@router.post("", response_model=MetadataToolOut)
def create_tool(body: ToolCreate, db: Session = Depends(get_db)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tool name is required")
    if db.query(MetadataTool).filter(MetadataTool.name == name).first():
        raise HTTPException(status_code=400, detail="A tool with this name already exists")

    tool = MetadataTool(
        name=name,
        type=body.type or "custom",
        host=body.host or None,
        config=body.config or {},
        status="CONNECTED",
        is_default=False,
    )
    db.add(tool)
    db.flush()

    if body.seed_demo:
        tools_service.seed_demo_catalog(db, tool)
    db.commit()
    return _tool_out(db, tool)


@router.delete("/{id}", status_code=204)
def delete_tool(id: str, db: Session = Depends(get_db)):
    tool = db.get(MetadataTool, id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.is_default:
        raise HTTPException(status_code=400, detail="The default tool cannot be deleted")

    # Remove the tool's tables and their findings (columns cascade).
    fqns = [t.fqn for t in db.query(CatalogTable).filter(CatalogTable.tool_id == id).all()]
    for fqn in fqns:
        db.query(Finding).filter(Finding.entity == fqn).delete(synchronize_session=False)
        db.query(Finding).filter(Finding.entity.like(f"{fqn}.%")).delete(synchronize_session=False)
    db.query(CatalogTable).filter(CatalogTable.tool_id == id).delete(synchronize_session=False)
    db.delete(tool)
    db.commit()
    return None
