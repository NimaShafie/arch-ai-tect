# server/services/run_build_nav.py

from pathlib import Path

from server.services.mkdocs_nav import build_nav


# Where all per-project docs live, relative to repo root
PROJECTS_ROOT = Path("docs") / "projects"

# Files we expect under each project, grouped by section
# NOTE: these names are aligned with docs/projects/*/package
PACKAGE_FILES = [
    ("Architecture Spec", "spec.md"),
    ("Software Requirements Spec (SRS)", "srs.md"),
    ("Reference Architecture", "reference-arch.md"),
    ("Implementation Guide", "implementation-guide.md"),
]

# NOTE: these names are aligned with docs/projects/*/diagrams
DIAGRAM_FILES = [
    ("C4 Context", "c4_context.md"),
    ("C4 Container", "c4_container.md"),
    ("C4 Component", "c4_component.md"),
    ("Logical View", "logical.md"),
    ("Deployment View", "deployment.md"),
    ("Sequence Diagram", "sequence.md"),
]


def _read_without_leading_title(path: Path) -> str:
    """
    Read a markdown file and strip a single leading ATX heading line
    (e.g. '# Architecture Spec') so that we can inject our own
    '### Architecture Spec' heading in the combined page.

    If no heading is found on the first line, return the content as-is.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if lines and lines[0].lstrip().startswith("#"):
        # Drop the first line + any immediate empty lines
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    return "\n".join(lines).strip()


def build_project_indexes() -> None:
    """
    For every docs/projects/<slug>/ directory, build a single index.md that
    inlines all package + diagram pages.

    The resulting structure is:

    # <Project Name>

    This is the architecture workspace for this project.

    ## Package
    ### Architecture Spec
    ...content...

    ## Diagrams
    ### C4 Context
    ...content...
    """
    if not PROJECTS_ROOT.exists():
        print(f"[build_project_indexes] No {PROJECTS_ROOT} directory, skipping.")
        return

    for project_dir in sorted(PROJECTS_ROOT.iterdir()):
        if not project_dir.is_dir():
            continue

        slug = project_dir.name

        # Try to infer a nicer title from an existing title.txt, otherwise slug
        title = slug.replace("-", " ").title()
        title_file = project_dir / "title.txt"
        if title_file.exists():
            custom_title = title_file.read_text(encoding="utf-8").strip()
            if custom_title:
                title = custom_title

        print(f"[build_project_indexes] Building combined index for project '{slug}'")

        lines: list[str] = []

        # Top-level title + intro
        lines.append(f"# {title}")
        lines.append("")
        lines.append("This is the architecture workspace for this project.")
        lines.append("")

        # ----- Package section -----
        lines.append("## Package")
        lines.append("")

        package_root = project_dir / "package"
        for section_title, filename in PACKAGE_FILES:
            src = package_root / filename
            if not src.exists():
                continue

            lines.append(f"### {section_title}")
            lines.append("")

            body = _read_without_leading_title(src)
            if body:
                lines.append(body)
                lines.append("")

        # visual separation between sections
        lines.append("---")
        lines.append("")

        # ----- Diagrams section -----
        lines.append("## Diagrams")
        lines.append("")

        diagrams_root = project_dir / "diagrams"
        for section_title, filename in DIAGRAM_FILES:
            src = diagrams_root / filename
            if not src.exists():
                continue

            lines.append(f"### {section_title}")
            lines.append("")

            body = _read_without_leading_title(src)
            if body:
                lines.append(body)
                lines.append("")

        index_path = project_dir / "index.md"
        index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

        print(f"[build_project_indexes] Wrote {index_path}")


def main() -> None:
    print("Running build_nav() before starting mkdocs serve...")
    build_nav()
    print("Done.")

    print("Building combined project index pages...")
    build_project_indexes()
    print("Done building project index pages.")


if __name__ == "__main__":
    main()
