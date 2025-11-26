# server/routers/ui.py

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slugify import slugify
from sqlmodel import select

from ..db import get_session
from ..models import Project
from ..schemas import ProjectCreate
from ..services.mkdocs_nav import build_nav

# Local templates instance to avoid circular import with server.app
templates = Jinja2Templates(directory="server/templates")

router = APIRouter(tags=["ui"])


# ---------------------------------------------------------------------
# HTML UI ROUTES
# ---------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui_home(request: Request, session=Depends(get_session)):
    """
    GET /  -> Workbench dashboard (project list)

    This is what you currently see at https://workbench.shafie.org/
    because the app mounts this router at the root with no prefix.
    """
    projects = session.exec(
        select(Project).order_by(Project.created_at.desc())
    ).all()

    return templates.TemplateResponse(
        "ui.html",
        {
            "request": request,
            "projects": projects,
        },
    )


@router.get("/ui/{slug}", response_class=HTMLResponse, include_in_schema=False)
def ui_project(slug: str, request: Request, session=Depends(get_session)):
    """
    GET /ui/{slug}  -> Project detail page (e.g., /ui/disney-ai-v3)

    IMPORTANT: We put the `/ui/` part *inside* the path here,
    because the router is currently included with NO prefix.
    """
    project = session.exec(
        select(Project).where(Project.slug == slug)
    ).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project with slug '{slug}' not found",
        )

    # build_nav is global, so we call it with no args. It can still
    # return per-project URLs based on manifest.yaml + mkdocs config.
    docs_urls = build_nav()

    return templates.TemplateResponse(
        "ui_project.html",
        {
            "request": request,
            "project": project,
            "docs_urls": docs_urls,
        },
    )


# ---------------------------------------------------------------------
# JSON API ROUTES (used by the UI JS)
# ---------------------------------------------------------------------


@router.get("/api/projects")
def api_list_projects(session=Depends(get_session)):
    """
    GET /api/projects -> JSON list of projects.

    Used by the UI JS to refresh the project table without needing to
    hard-code anything in mkdocs.yml. Returns a minimal shape that is
    stable for the front-end.
    """
    projects = session.exec(
        select(Project).order_by(Project.created_at.desc())
    ).all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "nav_title": getattr(p, "nav_title", p.name),
            "created_at": getattr(p, "created_at", None),
        }
        for p in projects
    ]


@router.post("/api/projects")
def api_create_project(payload: ProjectCreate, session=Depends(get_session)):
    """
    POST /api/projects -> create a new project.

    - If `slug` is omitted or empty, derive it from `name` via slugify.
    - If the slug already exists, return HTTP 400.
    - No mkdocs.yml changes and no hard-coded slugs; downstream
      tooling (ensure_project_tree, build_nav, etc.) can react to the
      new DB row and manifests as needed.
    """
    if not payload.name:
        raise HTTPException(status_code=400, detail="Project name is required")

    # Derive slug if not provided
    slug = (payload.slug or "").strip()
    if not slug:
        slug = slugify(payload.name)

    if not slug:
        raise HTTPException(status_code=400, detail="Could not derive slug from name")

    # Ensure slug is unique
    existing = session.exec(
        select(Project).where(Project.slug == slug)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")

    nav_title = (payload.nav_title or payload.name).strip() or payload.name

    project = Project(
        name=payload.name,
        slug=slug,
        nav_title=nav_title,
    )

    session.add(project)
    session.commit()
    session.refresh(project)

    # Optional: trigger any nav regeneration / manifest updates that
    # rely only on the DB + docs tree. If build_nav() has side-effects
    # (like writing _generated_projects_nav.yml), this will keep
    # mkdocs in sync without hard-coding slugs.
    try:
        build_nav()
    except Exception:
        # Don't fail project creation if nav regeneration blows up;
        # the docs site can be rebuilt separately.
        pass

    return {
        "status": "ok",
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "nav_title": project.nav_title,
    }
