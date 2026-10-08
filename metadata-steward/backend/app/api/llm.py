"""LLM prompt preview endpoint (for the editable-prompt feature)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import PromptPreviewOut, PromptPreviewRequest
from ..services.agents import build_prompt_preview

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.post("/prompt-preview", response_model=PromptPreviewOut)
def prompt_preview(body: PromptPreviewRequest, db: Session = Depends(get_db)):
    """Return the default system/user prompts for a generation target.

    The frontend shows these in the editable-prompt dialog (only when the
    ``enable_prompt_editing`` flag is on) before the user regenerates.
    """
    try:
        system, user = build_prompt_preview(db, body.kind, body.fqn, body.column)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return PromptPreviewOut(
        system_prompt=system,
        user_prompt=user,
        provider=settings.llm_provider,
        model=settings.openai_model,
    )
