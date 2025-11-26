# server/routers/ui.py

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from ..db import get_session
from ..models import Project
from ..services.mkdocs_nav import build_nav

# Local templates instance to avoid circular import with server.app
templates = Jinja2Templates(directory="server/templates")

router = APIRouter()


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

    # build_nav is global, so we call it with no args
    docs_urls = build_nav()

    return templates.TemplateResponse(
        "ui_project.html",
        {
            "request": request,
            "project": project,
            "docs_urls": docs_urls,
        },
    )
