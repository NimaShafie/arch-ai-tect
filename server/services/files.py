# server/services/files.py
from __future__ import annotations

from pathlib import Path
import json
import yaml
import os
import subprocess
from typing import Any, Dict, Optional

# -----------------------------------------------------------------------------#
# Constants
# -----------------------------------------------------------------------------#
DOCS_DIR = Path("docs")
PROJECTS_DIR = DOCS_DIR / "projects"

INDEX_TEMPLATE = """# {title}

This space is scaffolded and ready.

**Next steps (in the Workbench UI):**
1. Fill the high-level brief → {ui_base}/ui/{slug}#brief
2. Choose diagram types & dialects → {ui_base}/ui/{slug}#choices
3. Generate artifacts → {ui_base}/ui/{slug}#generate

Once generated, diagrams and specifications will appear here under this project.
"""

# -----------------------------------------------------------------------------#
# Public API
# -----------------------------------------------------------------------------#
def ensure_project_tree(
    slug: str,
    name: Optional[str] = None,
    nav_title: Optional[str] = None
) -> Path:
    """
    Ensure docs/projects/<slug>/ exists with an index.md and a stub manifest.yaml.
    Safe to call many times. Returns the project directory path.
    """
    pdir = PROJECTS_DIR / slug
    pdir.mkdir(parents=True, exist_ok=True)

    # Landing page
    index_md = pdir / "index.md"
    if not index_md.exists():
        ui_base = os.getenv("UI_BASE", "https://workbench.shafie.org")
        title = name or slug.replace("-", " ").title()
        index_md.write_text(
            INDEX_TEMPLATE.format(title=title, slug=slug, ui_base=ui_base),
            encoding="utf-8",
        )

    # Minimal manifest for nav/title + sane defaults so MkDocs builds cleanly
    manifest = pdir / "manifest.yaml"
    if not manifest.exists():
        manifest.write_text(
            yaml.safe_dump(
                {
                    "slug": slug,
                    "name": name or slug.replace("-", " ").title(),
                    "nav_title": nav_title or name or slug.replace("-", " ").title(),
                    "diagram_types": ["c4-context", "c4-container", "deployment", "sequence", "logical"],
                    "dialects": ["structurizr", "plantuml", "mermaid"],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    # Optionally kick a docs rebuild on first scaffold
    try:
        trigger_mkdocs_rebuild()
    except Exception:
        # never crash caller
        pass

    return pdir


# Back-compat shim (older code may import this)
def render_project_index(slug: str, title: Optional[str] = None) -> Path:
    """
    Backwards-compatible helper used by older orchestrators.
    Simply calls ensure_project_tree() which writes index.md.
    """
    return ensure_project_tree(slug=slug, name=title)


def write_json(path: Path, data: Dict[str, Any]):
    """
    Write a JSON file (pretty) and trigger a docs rebuild if under docs/.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _maybe_rebuild(path)


def write_yaml(path: Path, data: Dict[str, Any]):
    """
    Write a YAML file and trigger a docs rebuild if under docs/.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _maybe_rebuild(path)


# -----------------------------------------------------------------------------#
# Rebuild helpers
# -----------------------------------------------------------------------------#
def trigger_mkdocs_rebuild():
    """
    If MKDOCS_BUILD_CMD is set (e.g. 'mkdocs build --clean -q' or 'make docs'),
    run it asynchronously. No-op if unset.
    """
    cmd = os.getenv("MKDOCS_BUILD_CMD", "").strip()
    if not cmd:
        return
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # Never crash caller due to rebuild failures.
        pass


def _maybe_rebuild(path: Path):
    """
    Trigger a rebuild iff the written path is inside the docs/ tree.
    """
    try:
        resolved = path.resolve()
        if DOCS_DIR.resolve() in resolved.parents or resolved.parent == DOCS_DIR.resolve():
            trigger_mkdocs_rebuild()
    except Exception:
        # Never crash caller.
        pass
