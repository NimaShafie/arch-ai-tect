# server/routers/ui.py

from pathlib import Path
import shutil
import subprocess
import sys

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slugify import slugify
from sqlmodel import select

from server.db import get_session
from server.models import Project
from server.schemas import ProjectCreate
from server.services.mkdocs_nav import build_nav

# Local templates instance to avoid circular import with server.app
templates = Jinja2Templates(directory="server/templates")

router = APIRouter(tags=["ui"])

# Base path to docs/ so we can clean up per-project folders on delete
DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
REPO_ROOT = DOCS_ROOT.parent


def _trigger_docs_refresh() -> None:
    """
    Best-effort: run the same nav/index builder you currently call manually.

    This invokes:
        python -m server.services.run_build_nav

    which rebuilds the MkDocs project nav + combined project index pages.
    Any errors are swallowed so the UI doesn't break if docs rebuild fails.
    """
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "server.services.run_build_nav",
            ],
            cwd=str(REPO_ROOT),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # Don't break project create/delete flows if docs rebuild fails.
        # You can still run the command manually if needed.
        pass


# ---------------------------------------------------------------------
# HTML UI ROUTES
# ---------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui_home(request: Request, session=Depends(get_session)):
    """
    GET /  -> Workbench dashboard (project list)
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
# JSON API ROUTES (used by the UI JS on /ui)
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

    # Optional: regenerate nav (existing behavior)
    try:
        build_nav()
    except Exception:
        pass

    # NEW: best-effort full docs refresh (projects index + per-project index)
    _trigger_docs_refresh()

    return {
        "status": "ok",
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "nav_title": project.nav_title,
    }


@router.delete("/api/projects/{slug}")
def api_delete_project(slug: str, session=Depends(get_session)):
    """
    DELETE /api/projects/{slug} -> delete a project.

    This is what the "Delete" button on the dashboard calls.

    Behaviour:
    - 404 if the slug doesn't exist.
    - On success, removes the DB row.
    - Best-effort removal of docs/projects/<slug> (ignored if missing).
    - Best-effort nav regeneration.
    """
    project = session.exec(
        select(Project).where(Project.slug == slug)
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete from DB
    session.delete(project)
    session.commit()

    # Best-effort: remove docs/projects/<slug> directory
    try:
        proj_dir = DOCS_ROOT / "projects" / slug
        if proj_dir.is_dir():
            shutil.rmtree(proj_dir)
    except Exception:
        # Don't block deletion on filesystem issues
        pass

    # Existing: regenerate MkDocs nav
    try:
        build_nav()
    except Exception:
        pass

    # NEW: also rebuild combined project index pages so docs site updates
    _trigger_docs_refresh()

    return {"status": "ok", "slug": slug}
