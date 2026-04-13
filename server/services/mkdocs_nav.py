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


# -------------------------------------------------------------------
# Ensure project docs directory exists
# -------------------------------------------------------------------

def _ensure_docs_root() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# RENDER: Projects Index Page (rich layout – correct, non-indented)
# -------------------------------------------------------------------

def _render_projects_index(projects: List[Project]) -> str:
    """Render a clean, non-indented Markdown Projects page."""

    if not projects:
        return (
            "# Projects\n\n"
            "_No projects have been created yet via the Workbench UI._\n"
        )

    # Jump list
    jump_list = "\n".join(
        f"- [{p.name}](/projects/{p.slug}/)"
        for p in projects
    )

    # Detailed sections for each project
    sections: List[str] = []
    for p in projects:
        title = p.name
        slug = p.slug
        created = p.created_at.date().isoformat() if p.created_at else "—"

        section_md = (
            f"## [{title}](/projects/{slug}/)\n\n"
            f"**Created:** {created}  \n"
            f"**Slug:** `{slug}`  \n"
            f"**Summary:** Architecture workspace managed by the ArchAiTect Workbench.\n\n"
            "| Category     | Links |\n"
            "| ------------ | ----- |\n"
            f"| Package docs | [Spec](/projects/{slug}/package/spec.md) · "
            f"[SRS](/projects/{slug}/package/srs.md) · "
            f"[Ref Arch](/projects/{slug}/package/reference-arch.md) · "
            f"[Impl Guide](/projects/{slug}/package/implementation-guide.md) |\n"
            f"| Diagrams     | [C4 Context](/projects/{slug}/diagrams/c4_context.md) · "
            f"[C4 Container](/projects/{slug}/diagrams/c4_container.md) · "
            f"[C4 Component](/projects/{slug}/diagrams/c4_component.md) · "
            f"[Logical](/projects/{slug}/diagrams/logical.md) · "
            f"[Deployment](/projects/{slug}/diagrams/deployment.md) · "
            f"[Sequence](/projects/{slug}/diagrams/sequence.md) |\n"
        )

        sections.append(section_md)

    # Join all project sections
    sections_block = "\n\n---\n\n".join(sections)

    # Build full page (NO indentation!)
    final_md = (
        "# Projects\n\n"
        "These architecture projects are managed by the **ArchAiTect Workbench**.\n\n"
        "Use this page as the hub to jump into each project's package docs and diagrams.\n\n"
        "<div id=\"wb-projects\">\n\n"
        f"{jump_list}\n\n"
        "</div>\n\n"
        "---\n\n"
        f"{sections_block}\n"
    )

    return final_md


# -------------------------------------------------------------------
# WRITE: Projects index markdown file
# -------------------------------------------------------------------

def _write_projects_index(projects: List[Project]) -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    markdown = _render_projects_index(projects)
    (PROJECTS_ROOT / "index.md").write_text(markdown, encoding="utf-8")


# -------------------------------------------------------------------
# YAML generation for possible future use
# -------------------------------------------------------------------

def _write_generated_yaml(projects: List[Project]) -> None:
    payload: Dict[str, Any] = {
        "projects": [
            {
                "slug": p.slug,
                "title": p.name,
                "url": f"/projects/{p.slug}/",
            }
            for p in projects
        ]
    }
    GENERATED_YAML.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8"
    )


# -------------------------------------------------------------------
# Update mkdocs.yml navigation
# -------------------------------------------------------------------

def _update_mkdocs_nav(projects: List[Project]) -> None:
    if not MKDOCS_YML.exists():
        return

    cfg = yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8")) or {}

    cfg["nav"] = [
        {"Home": "index.md"},
        {"Projects": "projects/index.md"},
    ]

    MKDOCS_YML.write_text(
        yaml.safe_dump(cfg, sort_keys=False),
        encoding="utf-8"
    )


# -------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------

def build_nav() -> None:
    """
    Sync MkDocs with Workbench state:

    - Ensures docs/projects/<slug>/ exists
    - Creates stub index.md for each project (if missing)
    - Regenerates the rich Projects landing page
    - Updates mkdocs.yml nav
    - Regenerates generated YAML
    """

    _ensure_docs_root()

    with get_session() as session:
        projects: List[Project] = list(
            session.exec(select(Project).order_by(Project.created_at.asc()))
        )

    # Ensure each project folder & stub page exists
    for p in projects:
        project_dir = PROJECTS_ROOT / p.slug
        project_dir.mkdir(parents=True, exist_ok=True)

        index_md = project_dir / "index.md"
        if not index_md.exists():
            title = p.name
            index_md.write_text(
                f"# {title}\n\n"
                "This is the architecture workspace for this project.\n\n"
                "## Package\n\n"
                "- [Architecture Spec](./package/spec.md)\n"
                "- [Software Requirements Spec (SRS)](./package/srs.md)\n"
                "- [Reference Architecture](./package/reference-arch.md)\n"
                "- [Implementation Guide](./package/implementation-guide.md)\n\n"
                "## Diagrams\n\n"
                "- Diagrams are available under the `diagrams/` section of the docs.\n",
                encoding="utf-8",
            )

    # Regenerate full Projects page
    _write_projects_index(projects)

    # Update helper YAML
    _write_generated_yaml(projects)

    # Update mkdocs navigation
    _update_mkdocs_nav(projects)
