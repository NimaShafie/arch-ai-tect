# server/routers/brief.py

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Reuse the OpenWebUI integration & response-normalization logic
from .brief_ai import _call_openwebui, _extract_brief_from_response

router = APIRouter()


class BriefInterpretRequest(BaseModel):
    prompt: str


class BriefSaveRequest(BaseModel):
    brief: dict


@router.post("/projects/{slug}/brief/interpret")
async def interpret_brief(slug: str, body: BriefInterpretRequest):
    """
    Calls the AI backend (OpenWebUI) to interpret the natural-language
    prompt and produce structured brief.json for this project.

    This keeps the same URL shape as before:
      POST /api/projects/{slug}/brief/interpret
    (because app.py mounts this router under prefix="/api").
    """
    # 1) Call OpenWebUI via the helper in brief_ai.py
    data = await _call_openwebui(body.prompt)

    # 2) Normalize into our "brief" shape
    brief = _extract_brief_from_response(data)

    # 3) Persist to docs tree so MkDocs & the UI can read it
    path = Path(f"docs/projects/{slug}/brief.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, indent=2))

    return {"status": "ok", "brief": brief}


@router.post("/projects/{slug}/brief")
async def save_brief(slug: str, body: BriefSaveRequest):
    """
    Saves manually edited brief.json from the UI.

    URL: POST /api/projects/{slug}/brief
    """
    path = Path(f"docs/projects/{slug}/brief.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body.brief, indent=2))

    return {"status": "saved"}


@router.get("/projects/{slug}/brief")
async def get_brief(slug: str):
    """
    Returns the current brief.json if it exists.

    URL: GET /api/projects/{slug}/brief
    """
    path = Path(f"docs/projects/{slug}/brief.json")
    if not path.exists():
        return {"brief": {}}

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid brief.json for project '{slug}': {exc}",
        )

    return {"brief": data}
