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
        "Architecture workspaces managed by the **ArchAiTect Workbench**.",
        "",
        "Use this page as the hub to jump into each project's package docs and diagrams.",
        "",
    ]

    if not projects:
        lines.append("_No projects have been created yet via the Workbench UI._")
    else:
        for p in projects:
            title = (p.nav_title or p.name).strip() if getattr(p, "nav_title", None) else p.name
            slug = p.slug
            created = (
                p.created_at.date().isoformat()
                if getattr(p, "created_at", None)
                else "—"
            )
            summary = (
                p.summary.strip()
                if getattr(p, "summary", None)
                else "Architecture workspace managed by the ArchAiTect Workbench."
            )

            lines += [
                "---",
                "",
                f"### [{title}](./{slug}/index.md)",
                "",
                f"**Created:** {created}  ",
                f"**Slug:** `{slug}`  ",
                f"**Summary:** {summary}",
                "",
                "| Category | Links |",
                "| --- | --- |",
                (
                    f"| Package docs | "
                    f"[Spec](./{slug}/package/spec.md) · "
                    f"[SRS](./{slug}/package/srs.md) · "
                    f"[Ref Arch](./{slug}/package/reference-arch.md) · "
                    f"[Impl Guide](./{slug}/package/implementation-guide.md) |"
                ),
                (
                    f"| Diagrams | "
                    f"[C4 Context](./{slug}/diagrams/c4_context.md) · "
                    f"[C4 Container](./{slug}/diagrams/c4_container.md) · "
                    f"[C4 Component](./{slug}/diagrams/c4_component.md) · "
                    f"[Logical](./{slug}/diagrams/logical.md) · "
                    f"[Deployment](./{slug}/diagrams/deployment.md) · "
                    f"[Sequence](./{slug}/diagrams/sequence.md) |"
                ),
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

    We now keep nav *very* simple and move navigation to the top bar:

      - Home
      - Projects  (just the overview page)

    Individual projects are navigated from the Projects overview and the
    right-hand Table of contents, not from the left sidebar.
    """
    if not MKDOCS_YML.exists():
        return

    cfg = yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8")) or {}

    # Primary nav only has Home and Projects
    nav: List[Any] = [
        {"Home": "index.md"},
        {"Projects": "projects/index.md"},
    ]
    cfg["nav"] = nav

    # Theme tweaks: tabs at the top, no "expand" sidebar behaviour
    theme = cfg.get("theme") or {}
    features = set(theme.get("features") or [])

    # Top navigation tabs instead of left-hand tree
    features.update({"navigation.tabs", "navigation.top"})
    # We aren't using the expandable sidebar nav any more
    features.discard("navigation.expand")

    theme["features"] = sorted(features)
    cfg["theme"] = theme

    # Make sure the brand points to the public docs URL
    # (this also makes the "ArchAiTect Workbench" title a link home)
    cfg.setdefault("site_url", "https://docs.shafie.org/")

    MKDOCS_YML.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def build_nav() -> None:
    """
    Main entry point: keep MkDocs in sync with the Workbench projects.

    - Ensures docs/projects/ exists.
    - Ensures docs/projects/<slug>/ exists and writes a standard index.md
      for each project (idempotent, but will overwrite old generated content).
    - Regenerates docs/projects/index.md with a compact overview.
    - Writes docs/_generated_projects_nav.yml.
    - Rewrites mkdocs.yml nav from the Project table.
    """
    _ensure_docs_root()

    with get_session() as session:
        projects: List[Project] = list(
            session.exec(select(Project).order_by(Project.created_at.asc()))
        )

    # Project detail pages: always rewrite to keep them consistent
    for p in projects:
        project_dir = PROJECTS_ROOT / p.slug
        project_dir.mkdir(parents=True, exist_ok=True)

        index_md = project_dir / "index.md"
        title = (p.nav_title or p.name).strip() if getattr(p, "nav_title", None) else p.name

        content_lines = [
            f"# {title}",
            "",
            "This is the architecture workspace for this project.",
            "",
            "## Package",
            "",
            "- [Architecture Spec](./package/spec.md)",
            "- [Software Requirements Spec (SRS)](./package/srs.md)",
            "- [Reference Architecture](./package/reference-arch.md)",
            "- [Implementation Guide](./package/implementation-guide.md)",
            "",
            "## Diagrams",
            "",
            "- [C4 Context](./diagrams/c4_context.md)",
            "- [C4 Container](./diagrams/c4_container.md)",
            "- [C4 Component](./diagrams/c4_component.md)",
            "- [Logical View](./diagrams/logical.md)",
            "- [Deployment View](./diagrams/deployment.md)",
            "- [Sequence Diagram](./diagrams/sequence.md)",
            "",
        ]
        index_md.write_text("\n".join(content_lines), encoding="utf-8")

    _write_projects_index(projects)
    _write_generated_yaml(projects)
    _update_mkdocs_nav(projects)
