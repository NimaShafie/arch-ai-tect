# server/core/projects.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml, json
from slugify import slugify
from sqlalchemy.exc import OperationalError

from ..db import get_session
from ..models import Project, User
from .session import guest_temps

PROJECTS_DIR = Path("docs/projects")

@dataclass
class TempProject:
    slug: str
    name: str
    nav_title: str
    created_at: datetime

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def unique_slug_for_user(raw_slug: str, user: Optional[User]) -> str:
    base = slugify(raw_slug) or "project"
    n = 0
    with get_session() as s:
        while True:
            cand = base if n == 0 else f"{base}-{n+1}"
            try:
                if user:
                    exists = s.query(Project).filter(Project.slug == cand, Project.user_id == user.id).first()
                else:
                    exists = s.query(Project).filter(Project.slug == cand).first()
            except OperationalError:
                exists = s.query(Project).filter(Project.slug == cand).first()
            disk_exists = (PROJECTS_DIR / cand).exists()
            if not exists and not disk_exists:
                return cand
            n += 1

def find_existing_slug(raw_slug: str, user: Optional[User], request=None) -> Optional[str]:
    """Return an existing slug if the name/slug already exists (DB or guest temp)."""
    cand = slugify(raw_slug) or "project"
    with get_session() as s:
        try:
            if user:
                p = s.query(Project).filter(Project.slug == cand, Project.user_id == user.id).first()
                if p:
                    return p.slug
            p = s.query(Project).filter(Project.slug == cand, Project.user_id.is_(None)).first()
            if p:
                return p.slug
        except OperationalError:
            p = s.query(Project).filter(Project.slug == cand).first()
            if p:
                return p.slug

    if request and cand in guest_temps(request) and (PROJECTS_DIR / cand).exists():
        return cand
    return None

def temp_from_disk(slug: str) -> Optional[TempProject]:
    base = PROJECTS_DIR / slug
    if not base.exists(): return None
    mf = base / "manifest.yaml"
    name = slug.replace("-", " ").title()
    nav = name
    if mf.exists():
        try:
            data = yaml.safe_load(mf.read_text("utf-8")) or {}
            name = data.get("name", name)
            nav  = data.get("nav_title", nav)
        except Exception:
            pass
    return TempProject(slug=slug, name=name, nav_title=nav, created_at=datetime.fromtimestamp(base.stat().st_ctime))

def get_project_or_404(slug: str, user: Optional[User], request=None):
    with get_session() as s:
        try:
            if user:
                p = s.query(Project).filter(Project.slug == slug, Project.user_id == user.id).first()
                if p: return p
            p = s.query(Project).filter(Project.slug == slug, Project.user_id.is_(None)).first()
        except OperationalError:
            p = s.query(Project).filter(Project.slug == slug).first()
        if p: return p

    if request and slug in guest_temps(request):
        t = temp_from_disk(slug)
        if t: return t
    from fastapi import HTTPException
    raise HTTPException(404, f"Project '{slug}' not found")

def safe_load_brief(base: Path) -> str:
    f = base / "brief.json"
    if not f.exists(): return "{}"
    try:
        json.loads(f.read_text("utf-8"))  # validate
        return f.read_text("utf-8")
    except Exception:
        return "{}"

def safe_load_choices(base: Path) -> Dict[str, Any]:
    f = base / "manifest.yaml"
    if not f.exists(): return {"types": [], "dialects": []}
    try:
        data = yaml.safe_load(f.read_text("utf-8")) or {}
        return {"types": data.get("diagram_types", []) or [], "dialects": data.get("dialects", []) or []}
    except Exception:
        return {"types": [], "dialects": []}
