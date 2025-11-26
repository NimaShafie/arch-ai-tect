# server/services/mkdocs_nav.py

from pathlib import Path
from typing import Any, Dict, List

import yaml
from sqlmodel import select

from server.db import get_session
from server.models import Project

DOCS_ROOT = Path("docs")
PROJECTS_ROOT = DOCS_ROOT / "projects"
GENERATED_YAML = DOCS_ROOT / "_generated_projects_nav.yml"
MKDOCS_YML = Path("mkdocs.yml")


def _ensure_docs_root() -> None:
    """Ensure docs/projects exists."""
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


def _write_projects_index(projects: List[Project]) -> None:
    """
    Regenerate docs/projects/index.md from the DB.

    This is what you see at https://docs.shafie.org/projects/.
    No project names or slugs are hard-coded here; everything
    comes from the Project rows.
    """
    lines: List[str] = [
        "# Projects",
        "",
        "These architecture workspaces are managed by the **ArchAiTect Workbench**.",
        "",
        "Use this page as a starting point to jump into each project's package docs and diagrams.",
        "",
    ]

    if not projects:
        lines.append("_No projects have been created yet via the Workbench UI._")
    else:
        for p in projects:
            title = (p.nav_title or p.name).strip() if getattr(p, "nav_title", None) else p.name
            slug = p.slug

            lines += [
                "---",
                "",
                f"## {title}",
                "",
                f"- **Slug:** `{slug}`",
                f"- **Open docs:** [{title}](./{slug}/index.md)",
                "",
            ]

    lines.append("")
    (PROJECTS_ROOT / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _write_generated_yaml(projects: List[Project]) -> None:
    """
    Write docs/_generated_projects_nav.yml so MkDocs macros
    (if we ever want them) can list projects dynamically.
    """
    payload: Dict[str, Any] = {
        "projects": [
            {
                "slug": p.slug,
                "title": (p.nav_title or p.name).strip()
                if getattr(p, "nav_title", None)
                else p.name,
                "url": f"/projects/{p.slug}/",
            }
            for p in projects
        ]
    }
    GENERATED_YAML.write_text(
        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
    )


def _update_mkdocs_nav(projects: List[Project]) -> None:
    """
    Rewrite the nav section of mkdocs.yml from the DB.

    The resulting nav looks like:

      - Home
      - Projects
          - <project 1>
          - <project 2>
          - All projects
      - Services
      - Catalog

    No project names or slugs are hard-coded; it's all driven
    by the Project table.
    """
    if not MKDOCS_YML.exists():
        return

    cfg = yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8")) or {}

    # Build the dynamic Projects submenu from DB rows
    project_items: List[Dict[str, str]] = []
    for p in projects:
        title = (p.nav_title or p.name).strip() if getattr(p, "nav_title", None) else p.name
        project_items.append({title: f"projects/{p.slug}/index.md"})

    # Always include a link back to the projects index page
    project_items.append({"All projects": "projects/index.md"})

    # Preserve everything else in mkdocs.yml, just replace nav
    nav: List[Any] = [
        {"Home": "index.md"},
        {"Projects": project_items},
        {"Services": "services/index.md"},
        {"Catalog": "catalog/index.md"},
    ]
    cfg["nav"] = nav

    # Make sure navigation.expand is enabled so the submenu is always open
    theme = cfg.get("theme") or {}
    features = list(theme.get("features") or [])
    if "navigation.expand" not in features:
        if "navigation.top" in features:
            idx = features.index("navigation.top") + 1
            features.insert(idx, "navigation.expand")
        else:
            features.insert(0, "navigation.expand")
    theme["features"] = features
    cfg["theme"] = theme

    MKDOCS_YML.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def build_nav() -> None:
    """
    Main entry point: keep MkDocs in sync with the Workbench projects.

    - Ensures docs/projects/ exists.
    - Ensures docs/projects/<slug>/ exists and has at least a stub index.md
      (but doesn't overwrite any existing generated content there).
    - Regenerates docs/projects/index.md with nicer UI text.
    - Writes docs/_generated_projects_nav.yml.
    - Rewrites mkdocs.yml nav from the Project table.
    """
    _ensure_docs_root()

    with get_session() as session:
        projects: List[Project] = list(
            session.exec(select(Project).order_by(Project.created_at.asc()))
        )

    # Make sure each project directory exists and has an index.md
    for p in projects:
        project_dir = PROJECTS_ROOT / p.slug
        project_dir.mkdir(parents=True, exist_ok=True)

        index_md = project_dir / "index.md"
        if not index_md.exists():
            title = (p.nav_title or p.name).strip() if getattr(p, "nav_title", None) else p.name
            index_md.write_text(
                f"# {title}\n\n"
                "TEST!!!!This project's documentation is managed by the ArchAiTect Workbench.\n\n"
                "Once diagrams and docs are generated from the Workbench UI, "
                "they will appear here.\n",
                encoding="utf-8",
            )

    _write_projects_index(projects)
    _write_generated_yaml(projects)
    _update_mkdocs_nav(projects)
