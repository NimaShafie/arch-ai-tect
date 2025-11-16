# server/app.py
from pathlib import Path
import json
import yaml
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slugify import slugify

from .db import init_db, get_session
from .models import Project, Artifact  # Artifact kept for future use
from .schemas import ProjectCreate, BriefIn, DiagramChoices, GenerateRequest
from .services.files import ensure_project_tree, write_json, write_yaml
from .services.orchestrator import generate_all
from .services.mkdocs_nav import build_nav

# -----------------------------------------------------------------------------
# App & Templating
# -----------------------------------------------------------------------------
app = FastAPI(title="Architecture Workbench Registry")

templates = Jinja2Templates(directory="server/templates")

# Public docs base (used by the UI header); override via env if needed
DOCS_BASE = os.getenv("DOCS_BASE", "https://docs.shafie.org")

# tiny helper for templates
templates.env.globals["now"] = lambda: datetime.now()

# Initialize DB on import
init_db()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _ctx(request: Request, **extra):
    """
    Standard template context including docs_base & dynamic title support.
    """
    base = {"request": request, "docs_base": DOCS_BASE}
    base.update(extra)
    return base


def _get_project_or_404(slug: str) -> Project:
    with get_session() as s:
        p = s.query(Project).filter(Project.slug == slug).first()
        if not p:
            raise HTTPException(404, f"Project '{slug}' not found")
        return p


# -----------------------------------------------------------------------------
# Core JSON API (stable)
# -----------------------------------------------------------------------------
@app.post("/projects")
def create_project(data: ProjectCreate):
    slug = slugify(data.slug or data.name)
    nav_title = data.nav_title or data.name
    with get_session() as s:
        if s.query(Project).filter(Project.slug == slug).first():
            raise HTTPException(400, "Slug already exists")
        p = Project(slug=slug, name=data.name, nav_title=nav_title)
        s.add(p)
        s.commit()
        s.refresh(p)

    ensure_project_tree(slug)
    build_nav()

    return {
        "slug": slug,
        "nav_title": nav_title,
        "docs_url": f"/projects/{slug}/",
    }


@app.post("/projects/{slug}/brief")
def set_brief(slug: str, brief: BriefIn):
    ensure_project_tree(slug)
    write_json(Path(f"docs/projects/{slug}/brief.json"), brief.model_dump())
    return {"ok": True}


@app.post("/projects/{slug}/choices")
def set_choices(slug: str, choices: DiagramChoices):
    manifest = {
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "nav_title": slug.replace("-", " ").title(),
        "diagram_types": choices.types,
        "dialects": choices.dialects,
    }
    write_yaml(Path(f"docs/projects/{slug}/manifest.yaml"), manifest)
    return {"ok": True}


@app.post("/projects/{slug}/generate")
def generate(slug: str, req: GenerateRequest):
    base = Path(f"docs/projects/{slug}")
    brief = json.loads((base / "brief.json").read_text("utf-8"))
    manifest = yaml.safe_load((base / "manifest.yaml").read_text("utf-8"))
    out = generate_all(slug, brief, manifest, refine=req.refine)
    build_nav()
    return {"ok": True, "path": str(out), "docs_url": f"/projects/{slug}/"}


# -----------------------------------------------------------------------------
# Minimal HTML GUI (Option A)
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse, name="ui_home")
def ui_home(request: Request):
    return templates.TemplateResponse(
        "ui_home.html",
        _ctx(request, title="New Project · ArchAiTect"),
    )


@app.post("/ui/create", response_class=HTMLResponse)
def ui_create(
    request: Request,
    name: str = Form(...),
    slug: str = Form(""),
    nav_title: str = Form(""),
):
    # mirror /projects endpoint
    payload = {
        "name": name,
        "slug": slug or slugify(name),
        "nav_title": nav_title or name,
    }
    try:
        _ = create_project(ProjectCreate(**payload))
    except HTTPException as he:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=he.detail, title="Error · ArchAiTect"),
            status_code=he.status_code,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=str(e), title="Error · ArchAiTect"),
            status_code=400,
        )

    return RedirectResponse(url=f"/ui/{payload['slug']}", status_code=303)


@app.get("/ui/{slug}", response_class=HTMLResponse)
def ui_project(request: Request, slug: str):
    try:
        p = _get_project_or_404(slug)
    except HTTPException as he:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=he.detail, title="Not found · ArchAiTect"),
            status_code=he.status_code,
        )

    return templates.TemplateResponse(
        "ui_project.html",
        _ctx(
            request,
            title=f"{p.name} · ArchAiTect",
            project={"name": p.name, "slug": p.slug, "nav_title": p.nav_title},
            docs_url=f"/projects/{p.slug}/",
        ),
    )


@app.post("/ui/{slug}/brief", response_class=HTMLResponse)
def ui_set_brief(request: Request, slug: str, brief_json: str = Form(...)):
    try:
        payload = json.loads(brief_json)
        _ = set_brief(slug, BriefIn(**payload))
        return RedirectResponse(url=f"/ui/{slug}?brief=ok", status_code=303)
    except HTTPException as he:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=he.detail, title="Error · ArchAiTect"),
            status_code=he.status_code,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=f"Brief invalid: {e}", title="Error · ArchAiTect"),
            status_code=400,
        )


@app.post("/ui/{slug}/choices", response_class=HTMLResponse)
def ui_set_choices(
    request: Request,
    slug: str,
    types: str = Form("c4-context,c4-container,deployment,sequence,logical"),
    dialects: str = Form("structurizr,plantuml,mermaid"),
):
    t = [x.strip() for x in types.split(",") if x.strip()]
    d = [x.strip() for x in dialects.split(",") if x.strip()]
    try:
        _ = set_choices(slug, DiagramChoices(types=t, dialects=d))
        return RedirectResponse(url=f"/ui/{slug}?choices=ok", status_code=303)
    except HTTPException as he:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=he.detail, title="Error · ArchAiTect"),
            status_code=he.status_code,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=f"Choices invalid: {e}", title="Error · ArchAiTect"),
            status_code=400,
        )


@app.post("/ui/{slug}/generate", response_class=HTMLResponse)
def ui_generate(request: Request, slug: str, refine: int = Form(1)):
    try:
        _ = generate(slug, GenerateRequest(refine=bool(refine)))
        return templates.TemplateResponse(
            "ui_done.html",
            _ctx(
                request,
                title="Generated · ArchAiTect",
                slug=slug,
                link_href=f"{DOCS_BASE}/projects/{slug}/",
                link_text="Open in Docs",
                message="Artifacts generated and docs updated.",
                heading="Success",
            ),
        )
    except HTTPException as he:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=he.detail, title="Error · ArchAiTect"),
            status_code=he.status_code,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "ui_error.html",
            _ctx(request, detail=f"Generate failed: {e}", title="Error · ArchAiTect"),
            status_code=500,
        )
