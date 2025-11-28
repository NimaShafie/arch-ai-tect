# server/services/pipeline_sync.py

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from slugify import slugify

from server.services.run_build_nav import (
    PROJECTS_ROOT,
    DIAGRAM_FILES,
    PLANTUML_SERVER_BASE,
    encode_plantuml,
    _PLANTUML_BLOCK_RE,
)


class PipelineSyncError(Exception):
    pass


def _get_repo_dir() -> Path:
    repo_dir_env = os.environ.get("PIPELINE_REPO_DIR")
    if not repo_dir_env:
        raise PipelineSyncError(
            "PIPELINE_REPO_DIR environment variable is not set. "
            "It must point to a local clone of SevDev21/disney-ai-plus."
        )
    repo_dir = Path(repo_dir_env).expanduser().resolve()
    if not repo_dir.exists():
        raise PipelineSyncError(f"Pipeline repo directory does not exist: {repo_dir}")
    return repo_dir


def _run_git(repo_dir: Path, *args: str, check: bool = True) -> None:
    cmd = ["git", "-C", str(repo_dir), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise PipelineSyncError(
            f"git {' '.join(args)} failed: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _extract_pre_diagrams_markdown(project_dir: Path) -> str:
    """
    Take docs/projects/<slug>/index.md and return everything BEFORE the
    '### Diagrams' heading. This becomes docs/architecture/<slug>.md
    in the disney-ai-plus repo.
    """
    index_path = project_dir / "index.md"
    if not index_path.exists():
        raise PipelineSyncError(f"Project index not found: {index_path}")

    text = index_path.read_text(encoding="utf-8")
    parts = text.split("### Diagrams", 1)
    pre_diagrams = parts[0].strip()
    if not pre_diagrams:
        raise PipelineSyncError(
            f"No content found before '### Diagrams' in {index_path}"
        )
    return pre_diagrams


def _extract_plantuml_code(md_text: str) -> str | None:
    """
    Find the first ```plantuml``` (or ```kroki-plantuml```) code block
    and return just the PlantUML source inside it.
    """
    m = _PLANTUML_BLOCK_RE.search(md_text)
    if not m:
        return None
    return m.group(1).strip()


def _requirements_bullets_from_plantuml(code: str, title: str) -> list[str]:
    """Plain markdown bullet list (no HTML, no nested fences)."""
    bullets: list[str] = []
    lines = [ln.strip() for ln in code.splitlines()]

    for ln in lines:
        if not ln or ln.startswith("'"):
            continue
        if ln.lower().startswith("@startuml") or ln.lower().startswith("@enduml"):
            continue
        if ln.startswith("!"):
            continue

        # Sequence-style message: A -> B : message
        m = re.match(r"(\w+)\s*[-\.]+>\s*(\w+)\s*:(.+)", ln)
        if m:
            src, dst, msg = m.group(1), m.group(2), m.group(3).strip()
            bullets.append(
                f"- The system shall support an interaction where {src} sends "
                f"the message '{msg}' to {dst}, and this exchange shall be "
                f"implemented, logged, and testable end-to-end."
            )
            continue

        # C4 relationship: Rel(a, b, "Uses")
        m = re.match(r"Rel\(([^,]+),\s*([^,]+),\s*\"([^\"]+)\"", ln)
        if m:
            a, b, rel = (p.strip() for p in m.groups())
            bullets.append(
                f"- The architecture shall include a relationship where "
                f"{a} {rel.lower()} {b}; this connection must be implemented "
                f"with appropriate protocols, security, monitoring, and error handling."
            )
            continue

        # C4 elements
        m = re.match(
            r"(Person|System|Container|Component)\(([^,]+),\s*\"([^\"]+)\"(?:,\s*\"([^\"]+)\")?",
            ln,
        )
        if m:
            kind, ident, name, desc = m.groups()
            desc_part = f" ({desc})" if desc else ""
            bullets.append(
                f"- The design shall define a {kind.lower()} {ident} named {name}"
                f"{desc_part}, and implementation work must provision it as a "
                f"distinct deployable or conceptual element."
            )
            continue

        # Deployment-ish elements
        m = re.match(
            r"(node|database|artifact|component|rectangle|queue|cloud|storage)\s+\"([^\"]+)\"\s+as\s+(\w+)",
            ln,
            re.IGNORECASE,
        )
        if m:
            kind, name, alias = m.groups()
            bullets.append(
                f"- The deployment model shall include a {kind.lower()} {alias} "
                f"representing {name}; infrastructure tasks must provision, "
                f"secure, and monitor this element."
            )
            continue

    if not bullets:
        bullets.append(
            f"- The diagram titled '{title}' defines primary elements and "
            "relationships; implementation must ensure each element is realized "
            "in code, configuration, and infrastructure."
        )
        bullets.append(
            "- Non-functional requirements (performance, security, observability, "
            "resilience) must be applied to all components and links shown."
        )

    return bullets


def _build_diagram_doc(
    slug: str,
    diagram_title: str,
    plantuml_code: str,
) -> str:
    """
    Build the *GitHub-facing* diagram markdown.

    - Link to the PlantUML viewer.
    - Embed the PNG rendered by the PlantUML server.
    - Append a plain Markdown Requirements section.
    - Append the Source footer.
    """
    encoded = encode_plantuml(plantuml_code)
    viewer_url = f"{PLANTUML_SERVER_BASE}/uml/{encoded}"
    png_url = f"{PLANTUML_SERVER_BASE}/png/{encoded}"

    bullets = _requirements_bullets_from_plantuml(plantuml_code, diagram_title)
    source_url = f"https://workbench.shafie.org/projects/{slug}/"

    out: list[str] = []
    out.append(f"# {diagram_title}")
    out.append("")
    out.append(f"[Open in PlantUML]({viewer_url})")
    out.append("")
    out.append(f"![{diagram_title}]({png_url})")
    out.append("")
    out.append("## Requirements")
    out.append("")
    out.extend(bullets)
    out.append("")
    out.append("---")
    out.append("")
    out.append(
        f"_Source: generated from "
        f"[ArchAiTect Workbench]({source_url})_"
    )
    out.append("")

    return "\n".join(out)


def sync_project_to_pipeline(slug: str) -> dict:
    """
    Copy the current project's architecture + diagrams into the
    SevDev21/disney-ai-plus repo and git push.
    """
    project_dir = PROJECTS_ROOT / slug
    if not project_dir.exists():
        raise PipelineSyncError(
            f"Unknown project slug: {slug} (dir {project_dir} missing)"
        )

    repo_dir = _get_repo_dir()

    # Make sure we're up to date before writing
    _run_git(repo_dir, "fetch", "--all", check=True)
    _run_git(repo_dir, "pull", "--rebase", check=True)

    # ---- Architecture / package section (single file) -----------------------
    pre_diagrams_markdown = _extract_pre_diagrams_markdown(project_dir)

    # Look at the final non-blank line; if it's already '---',
    # don't add another horizontal rule before the footer.
    arch_dir = repo_dir / "docs" / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    arch_path = arch_dir / f"{slug}.md"

    source_url = f"https://workbench.shafie.org/projects/{slug}/"

    body = pre_diagrams_markdown.rstrip()
    lines = body.splitlines()
    last_non_blank = ""
    for line in reversed(lines):
        if line.strip():
            last_non_blank = line.strip()
            break

    if last_non_blank == "---":
        # Already has a trailing separator; just add footer.
        arch_text = (
            body.rstrip()
            + "\n\n"
            + f"_Source: generated from [ArchAiTect Workbench]({source_url})_\n"
        )
    else:
        # No trailing separator; insert one before footer.
        arch_text = (
            body.rstrip()
            + "\n\n---\n\n"
            + f"_Source: generated from [ArchAiTect Workbench]({source_url})_\n"
        )

    arch_path.write_text(arch_text, encoding="utf-8")

    # ---- Diagrams section (one file per diagram) ---------------------------
    diagrams_root = project_dir / "diagrams"
    diagrams_base_dir = repo_dir / "docs" / "diagrams" / slug
    diagrams_base_dir.mkdir(parents=True, exist_ok=True)

    written_diagrams: list[str] = []

    for diagram_title, filename in DIAGRAM_FILES:
        src = diagrams_root / filename
        if not src.exists():
            continue

        md_text = src.read_text(encoding="utf-8")
        code = _extract_plantuml_code(md_text)

        diagram_slug = slugify(diagram_title)
        out_path = diagrams_base_dir / f"{diagram_slug}.md"

        source_url = f"https://workbench.shafie.org/projects/{slug}/"

        if code:
            doc = _build_diagram_doc(slug, diagram_title, code)
        else:
            # Fallback: no PlantUML block found; just copy the body and
            # add a Source footer.
            body_fallback = md_text.strip()
            doc_lines: list[str] = []
            doc_lines.append(f"# {diagram_title}")
            doc_lines.append("")
            if body_fallback:
                doc_lines.append(body_fallback)
                doc_lines.append("")
            doc_lines.append("---")
            doc_lines.append("")
            doc_lines.append(
                f"_Source: generated from [ArchAiTect Workbench]({source_url})_"
            )
            doc_lines.append("")
            doc = "\n".join(doc_lines)

        out_path.write_text(doc, encoding="utf-8")
        written_diagrams.append(str(out_path.relative_to(repo_dir)))

    # Stage, commit, push
    _run_git(
        repo_dir,
        "add",
        "docs/architecture",
        "docs/diagrams",
        check=True,
    )
    # Commit can be empty; ignore non-zero return in that case
    _run_git(
        repo_dir,
        "commit",
        "-m",
        f"Sync architecture from ArchAiTect for {slug}",
        check=False,
    )
    _run_git(repo_dir, "push", check=True)

    return {
        "architecture_file": str(arch_path.relative_to(repo_dir)),
        "diagram_files": written_diagrams,
    }
