# server/routers/ui.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from slugify import slugify
from sqlmodel import select

from ..db import get_session
from ..models import Project
from ..services.orchestrator import generate_all
from ..services.mkdocs_nav import build_nav

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")

DOCS_BASE = "https://docs.shafie.org"
UI_BASE = "https://workbench.shafie.org"

def _docs_urls(slug: str) -> Dict[str, str]:
    base = f"{DOCS_BASE}/projects/{slug}"
    return {
        "project_home": base + "/",
        "package_spec": base + "/package/spec/",
        "package_srs": base + "/package/srs/",
        "package_ref": base + "/package/reference-arch/",
        "package_impl": base + "/package/implementation-guide/",
        "diagrams": base + "/diagrams/",
    }

@router.get("/", include_in_schema=False)
def ui_root():
    return RedirectResponse(url="/ui", status_code=303)

@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
@router.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
def ui_index(request: Request):
    # home page template that lists projects and create form
    # (kept the same filename to preserve styling)
    with get_session() as session:
        rows = session.exec(select(Project).order_by(Project.created_at.desc())).all()
    return templates.TemplateResponse(
        "ui.html",
        {"request": request, "projects": rows},
    )

# ---- Create project (GET & POST) -------------------------------------------
@router.api_route("/ui/create", methods=["GET", "POST"], include_in_schema=False)
def ui_create(
    request: Request,
    name: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    nav_title: Optional[str] = Form(None),
):
    if request.method != "POST":
        return RedirectResponse(url="/ui", status_code=303)

    final_slug = slugify((slug or name or "")).strip("-")
    if not final_slug:
        return RedirectResponse(url="/ui", status_code=303)

    final_title = (nav_title or name or final_slug).strip()

    with get_session() as session:
        exists: Optional[Project] = session.query(Project).filter(Project.slug == final_slug).first()
        if not exists:
            proj = Project(name=(name or final_title).strip(), slug=final_slug)
            if hasattr(proj, "nav_title"):
                setattr(proj, "nav_title", final_title)
            session.add(proj)
            session.commit()

    # soft-scaffold docs path so users see a placeholder
    proj_dir = Path("docs") / "projects" / final_slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    idx = proj_dir / "index.md"
    if not idx.exists():
        idx.write_text(
            f"# {final_title}\n\nThis space is scaffolded and ready.\n\n"
            "Use **Workbench → Generate** to populate artifacts and diagrams.",
            encoding="utf-8",
        )
    (proj_dir / "diagrams").mkdir(parents=True, exist_ok=True)

    try:
        build_nav()
    except Exception:
        pass

    return RedirectResponse(url=f"/ui/{final_slug}", status_code=303)

# ---- Project page ----------------------------------------------------------
@router.get("/ui/{slug}", response_class=HTMLResponse)
def ui_project(
    request: Request,
    slug: str,
    brief: Optional[str] = None,
    choices: Optional[str] = None,
    gen: Optional[str] = None,
    generr: Optional[str] = None,
):
    with get_session() as session:
        proj: Optional[Project] = session.query(Project).filter(Project.slug == slug).first()
    if not proj:
        proj = Project(name=slug.replace("-", " ").title(), slug=slug)

    docs_dir = Path("docs") / "projects" / slug
    brief_json = "{}"
    try:
        p = docs_dir / "brief.json"
        if p.exists():
            brief_json = p.read_text(encoding="utf-8")
    except Exception:
        brief_json = "{}"

    return templates.TemplateResponse(
        "ui_project.html",
        {
            "request": request,
            "project": {"name": proj.name, "slug": proj.slug},
            "brief_json": brief_json,
            "docs_urls": _docs_urls(slug),
            "flags": {
                "brief": bool(brief),
                "choices": bool(choices),
                "gen": bool(gen),
                "generr": bool(generr),
            },
            "ui_base": UI_BASE,
        },
    )

# ---- Brief & Choices -------------------------------------------------------
@router.post("/ui/{slug}/brief")
def save_brief(slug: str, brief_text: str = Form(...)):
    try:
        json.loads(brief_text)
    except json.JSONDecodeError:
        return RedirectResponse(url=f"/ui/{slug}#brief", status_code=303)

    proj_dir = Path("docs") / "projects" / slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "brief.json").write_text(brief_text, encoding="utf-8")
    return RedirectResponse(url=f"/ui/{slug}?brief=ok#brief", status_code=303)

@router.post("/ui/{slug}/choices")
def save_choices(
    slug: str,
    c4_context: Optional[str] = Form(None),
    c4_container: Optional[str] = Form(None),
    c4_component: Optional[str] = Form(None),
    sequence: Optional[str] = Form(None),
    deployment: Optional[str] = Form(None),
    logical: Optional[str] = Form(None),
):
    picked: List[str] = []
    if c4_context:   picked.append("c4_context")
    if c4_container: picked.append("c4_container")
    if c4_component: picked.append("c4_component")
    if sequence:     picked.append("sequence")
    if deployment:   picked.append("deployment")
    if logical:      picked.append("logical")

    manifest_path = Path("docs") / "projects" / slug / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("choices:\n" + "".join(f"  - {c}\n" for c in picked), encoding="utf-8")
    return RedirectResponse(url=f"/ui/{slug}?choices=ok#choices", status_code=303)

# ---- Generate (GET & POST) -------------------------------------------------
@router.api_route("/ui/{slug}/generate", methods=["GET", "POST"])
def generate(slug: str, refine: Optional[str] = Form(None)):
    docs_dir = Path("docs") / "projects" / slug

    brief_text = "{}"
    p = docs_dir / "brief.json"
    if p.exists():
        try:
            brief_text = p.read_text(encoding="utf-8")
            json.loads(brief_text)
        except Exception:
            return RedirectResponse(url=f"/ui/{slug}?generr=1#generate", status_code=303)

    choices: List[str] = []
    man = docs_dir / "manifest.yaml"
    if man.exists():
        try:
            for line in man.read_text(encoding="utf-8").splitlines():
                t = line.strip()
                if t.startswith("- "):
                    choices.append(t[2:].strip())
        except Exception:
            pass

    (docs_dir / "diagrams").mkdir(parents=True, exist_ok=True)
    if not (docs_dir / "diagrams" / "index.md").exists():
        (docs_dir / "diagrams" / "index.md").write_text(
            "# Diagrams\n\nGenerated diagrams will appear here.\n",
            encoding="utf-8",
        )

    with get_session() as session:
        proj: Optional[Project] = session.query(Project).filter(Project.slug == slug).first()
    project_name = proj.name if proj else slug.replace("-", " ").title()

    try:
        generate_all(
            project_slug=slug,
            project_name=project_name,
            brief_json=brief_text,
            choices=choices,
            refine=bool(refine),
        )
        try:
            build_nav()
        except Exception:
            pass
        return RedirectResponse(url=f"/ui/{slug}?gen=ok#generate", status_code=303)
    except Exception:
        return RedirectResponse(url=f"/ui/{slug}?generr=1#generate", status_code=303)

# ---- API: list/create/delete projects -------------------------------------
@router.get("/api/projects")
def api_list_projects():
    with get_session() as session:
        rows = session.exec(select(Project).order_by(Project.created_at.desc())).all()
    return [{"name": p.name, "slug": p.slug, "created_at": p.created_at} for p in rows]

@router.post("/api/projects")
def api_create_project(payload: dict):
    name = (payload or {}).get("name") or ""
    slug = (payload or {}).get("slug")
    nav_title = (payload or {}).get("nav_title")
    request = Request  # not used; keep consistent signature with form version
    return ui_create(request, name=name, slug=slug, nav_title=nav_title)

@router.delete("/api/projects/{slug}")
def api_delete_project(slug: str):
    # 1) delete from DB
    with get_session() as session:
        proj: Optional[Project] = session.query(Project).filter(Project.slug == slug).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        session.delete(proj)
        session.commit()

    # 2) remove docs directory (safe)
    proj_dir = Path("docs") / "projects" / slug
    if proj_dir.exists() and proj_dir.is_dir():
        # remove contents recursively
        for p in sorted(proj_dir.rglob("*"), reverse=True):
            try:
                p.unlink() if p.is_file() else p.rmdir()
            except Exception:
                pass
        try:
            proj_dir.rmdir()
        except Exception:
            pass

    # 3) rebuild nav (best-effort)
    try:
        build_nav()
    except Exception:
        pass

    return {"ok": True}
