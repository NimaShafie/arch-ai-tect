# server/routers/api.py
from fastapi import APIRouter, Request, Response, HTTPException
from pathlib import Path
import json, yaml

from ..schemas import ProjectCreate, BriefIn, DiagramChoices, GenerateRequest
from ..services.files import ensure_project_tree, write_yaml, write_json
from ..services.mkdocs_nav import build_nav
from ..services.orchestrator import generate_all
from ..db import get_session
from ..models import Project
from ..core.session import current_user, add_guest_temp
from ..core.projects import (
    PROJECTS_DIR, unique_slug_for_user, find_existing_slug, get_project_or_404
)

router = APIRouter()

@router.post("/projects")
def api_create(data: ProjectCreate, request: Request, response: Response):
    user = current_user(request)
    desired_name = data.name
    desired_slug = (data.slug or data.name).strip()

    # NEW: if exists, return it rather than creating -2, -3
    existing = find_existing_slug(desired_slug, user, request)
    if existing:
        return {"slug": existing, "nav_title": data.nav_title or desired_name, "docs_url": f"/projects/{existing}/"}

    slug = unique_slug_for_user(desired_slug, user)
    nav = data.nav_title or desired_name

    ensure_project_tree(slug, name=desired_name, nav_title=nav)
    write_yaml(PROJECTS_DIR / slug / "manifest.yaml", {
        "slug": slug, "name": desired_name, "nav_title": nav,
        "temporary": user is None,
    })

    if user:
        with get_session() as s:
            s.add(Project(slug=slug, name=desired_name, nav_title=nav, user_id=user.id))
            s.commit()
        try: build_nav()
        except Exception: pass
    else:
        add_guest_temp(response, request, slug)

    return {"slug": slug, "nav_title": nav, "docs_url": f"/projects/{slug}/"}

@router.post("/projects/{slug}/brief")
def api_brief(slug: str, brief: BriefIn, request: Request):
    _ = get_project_or_404(slug, current_user(request), request=request)
    write_json(PROJECTS_DIR / slug / "brief.json", brief.model_dump())
    return {"ok": True}

@router.post("/projects/{slug}/choices")
def api_choices(slug: str, choices: DiagramChoices, request: Request):
    _ = get_project_or_404(slug, current_user(request), request=request)
    write_yaml(PROJECTS_DIR / slug / "manifest.yaml", {
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "nav_title": slug.replace("-", " ").title(),
        "diagram_types": choices.types,
        "dialects": choices.dialects,
    })
    return {"ok": True}

@router.post("/projects/{slug}/generate")
def api_generate(slug: str, req: GenerateRequest, request: Request):
    _ = get_project_or_404(slug, current_user(request), request=request)
    base = PROJECTS_DIR / slug
    try: brief = json.loads((base / "brief.json").read_text("utf-8"))
    except Exception: raise HTTPException(400, "Brief not found or invalid.")
    try: manifest = yaml.safe_load((base / "manifest.yaml").read_text("utf-8"))
    except Exception: raise HTTPException(400, "Manifest not found or invalid.")

    out_dir = generate_all(slug, brief, manifest, refine=req.refine)
    if current_user(request):
        try: build_nav()
        except Exception: pass

    return {"ok": True, "path": str(out_dir), "docs_url": f"/projects/{slug}/"}
