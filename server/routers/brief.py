# server/routers/brief.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from server.db import get_session
from server.models import Project
from server.services.files import ensure_project_tree

router = APIRouter(
    prefix="/api/projects",
    tags=["brief"],
)

DOCS_ROOT = Path("docs/projects")


class BriefPayload(BaseModel):
    brief: Dict[str, Any]


def _get_project_or_404(slug: str, session) -> Project:
    """
    Fetch a Project by slug or raise HTTP 404.
    Uses the same select(...) pattern as ui.py.
    """
    project = session.exec(
        select(Project).where(Project.slug == slug)
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return project


def _brief_path(slug: str) -> Path:
    """Return docs/projects/{slug}/brief.json."""
    return DOCS_ROOT / slug / "brief.json"


@router.get("/{slug}/brief")
def get_brief(
    slug: str,
    session=Depends(get_session),
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    GET /api/projects/{slug}/brief

    Returns:
        { "brief": {...} }  if the file exists
        { "brief": null }   if it does not (no 404 in that case)
    """
    _get_project_or_404(slug, session)

    path = _brief_path(slug)
    if not path.exists():
        return {"brief": None}

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read brief for project '{slug}': {exc}",
        ) from exc

    return {"brief": data}


@router.post("/{slug}/brief")
def save_brief(
    slug: str,
    payload: BriefPayload,
    session=Depends(get_session),
) -> Dict[str, Any]:
    """
    POST /api/projects/{slug}/brief

    Body:
        { "brief": { ... } }

    Creates or overwrites docs/projects/{slug}/brief.json.
    """
    project = _get_project_or_404(slug, session)

    # Ensure docs tree is present for this project.
    try:
        ensure_project_tree(project.slug, project.name)
    except TypeError:
        # In case ensure_project_tree(slug) is the current signature.
        ensure_project_tree(project.slug)

    path = _brief_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        path.write_text(
            json.dumps(payload.brief, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save brief for project '{slug}': {exc}",
        ) from exc

    return {"status": "ok"}
