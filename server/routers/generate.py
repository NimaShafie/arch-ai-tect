# server/routers/generate.py

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.schemas import DiagramChoices
from server.services.orchestrator import generate_all

router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    # Matches payload from ui_project.html: { "diagrams": ["c4_context", ...] }
    diagrams: List[str]


class GenerateResponse(BaseModel):
    status: str
    diagrams: List[str]


def _to_diagram_choices(ids: List[str]) -> DiagramChoices:
    """
    Map the string IDs from the UI into the existing DiagramChoices schema.
    Any diagram not listed in `ids` is treated as False.
    """
    return DiagramChoices(
        c4_context="c4_context" in ids,
        c4_container="c4_container" in ids,
        c4_component="c4_component" in ids,
        sequence="sequence" in ids,
        deployment="deployment" in ids,
        logical="logical" in ids,
    )


@router.post("/api/projects/{slug}/generate", response_model=GenerateResponse)
async def generate_project(slug: str, body: GenerateRequest) -> GenerateResponse:
    """
    Trigger diagram + docs generation for a project slug.

    The UI sends a list of diagram IDs; we convert that into DiagramChoices
    and hand off to generate_all, which handles PlantUML/Kroki + MkDocs.
    """
    if not body.diagrams:
        raise HTTPException(status_code=400, detail="No diagram types provided")

    choices_model = _to_diagram_choices(body.diagrams)

    try:
        # Primary: new signature generate_all(slug, diagram_choices)
        try:
            generate_all(slug, choices_model)
        except TypeError:
            # Fallback: older signature generate_all(slug)
            generate_all(slug)
    except Exception as exc:
        # Surface as clean JSON error for the UI toast
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {exc}",
        ) from exc

    return GenerateResponse(status="ok", diagrams=body.diagrams)
