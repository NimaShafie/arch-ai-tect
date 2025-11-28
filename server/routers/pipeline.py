# server/routers/pipeline.py

from pathlib import Path
import os
import subprocess
from typing import List

from fastapi import APIRouter, HTTPException

from server.services.run_build_nav import (
    PROJECTS_ROOT,
    DIAGRAM_FILES,
    _read_without_leading_title,
    build_pipeline_diagram_markdown,
)

router = APIRouter(prefix="/api/projects", tags=["pipeline"])

# Default location of the Disney+ docs repo if PIPELINE_REPO_DIR is not set
DEFAULT_PIPELINE_REPO_DIR = "/home/n1mz/projects/disney-ai-plus"


def _git(args: List[str], cwd: Path) -> str:
    """Run a git command and return stdout, raising on failure."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _export_to_pipeline(slug: str) -> dict:
    """
    Core export logic used by both GET and POST endpoints.
    """
    repo_root = Path(".").resolve()
    project_dir = PROJECTS_ROOT / slug
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Unknown project slug")

    index_path = project_dir / "index.md"
    if not index_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Project index.md not found; run build_nav / docs build first.",
        )

    # Resolve pipeline repo directory, with a sensible default
    pipeline_repo_dir_env = os.getenv("PIPELINE_REPO_DIR", DEFAULT_PIPELINE_REPO_DIR)
    pipeline_repo_dir = Path(pipeline_repo_dir_env).resolve()
    if not pipeline_repo_dir.exists():
        raise HTTPException(
            status_code=500,
            detail=f"PIPELINE_REPO_DIR '{pipeline_repo_dir}' does not exist.",
        )

    # --- Architecture file: slice index.md between '### Package' and '### Diagrams'
    index_text = index_path.read_text(encoding="utf-8")
    pkg_marker = "\n### Package"
    diag_marker = "\n### Diagrams"
    pkg_pos = index_text.find(pkg_marker)
    diag_pos = index_text.find(diag_marker)

    if pkg_pos == -1:
        raise HTTPException(
            status_code=500,
            detail="Could not locate '### Package' section in project index.md",
        )

    if diag_pos == -1 or diag_pos <= pkg_pos:
        # If there is no diagrams section yet, treat rest of file as architecture.
        arch_body = index_text[pkg_pos:].strip()
    else:
        arch_body = index_text[pkg_pos:diag_pos].strip()

    # --- CLEAN UP trailing footer from the Workbench index so we don't
    #     get double '---' and double '_Source:' in the Disney repo.
    arch_lines = arch_body.splitlines()

    # remove trailing blank lines
    while arch_lines and not arch_lines[-1].strip():
        arch_lines.pop()

    # drop trailing '_Source: ...' line if present
    if arch_lines and arch_lines[-1].lstrip().startswith("_Source:"):
        arch_lines.pop()

    # drop any trailing horizontal rules
    while arch_lines and arch_lines[-1].strip() == "---":
        arch_lines.pop()

    arch_body_clean = "\n".join(arch_lines).rstrip()

    # Try to recover the nice project title from the index (## <Title>)
    title = slug.replace("-", " ").title()
    m = None
    for line in index_text.splitlines():
        if line.startswith("## "):
            m = line[3:].strip()
            break
    if m:
        title = m

    arch_rel_path = Path("docs") / "architecture" / f"{slug}.md"
    arch_abs = pipeline_repo_dir / arch_rel_path
    arch_abs.parent.mkdir(parents=True, exist_ok=True)

    arch_out_lines = [
        f"# Architecture – {title}",
        "",
        arch_body_clean,
        "",
        "---",
        "",
        f"_Source: generated from "
        f"[ArchAiTect Workbench](https://workbench.shafie.org/projects/{slug}/)_",
        "",
    ]
    arch_abs.write_text("\n".join(arch_out_lines).rstrip() + "\n", encoding="utf-8")

    diagram_rel_paths: list[str] = []

    # --- Diagrams: transform each PlantUML source into richer markdown
    diagrams_src_root = project_dir / "diagrams"
    diagrams_dst_root = pipeline_repo_dir / "docs" / "diagrams" / slug
    diagrams_dst_root.mkdir(parents=True, exist_ok=True)

    for section_title, filename in DIAGRAM_FILES:
        src_path = diagrams_src_root / filename
        if not src_path.exists():
            continue

        body = _read_without_leading_title(src_path)
        if not body:
            continue

        # CLEAN trailing footer from the diagram source as well
        diag_lines = body.splitlines()

        # remove trailing blank lines
        while diag_lines and not diag_lines[-1].strip():
            diag_lines.pop()

        # drop trailing '_Source: ...' if present
        if diag_lines and diag_lines[-1].lstrip().startswith("_Source:"):
            diag_lines.pop()

        # drop any trailing horizontal rules
        while diag_lines and diag_lines[-1].strip() == "---":
            diag_lines.pop()

        body_clean = "\n".join(diag_lines).rstrip()
        if not body_clean:
            continue

        rendered = build_pipeline_diagram_markdown(body_clean, section_title, slug)

        dst_rel = Path("docs") / "diagrams" / slug / filename
        dst_abs = pipeline_repo_dir / dst_rel
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        dst_abs.write_text(rendered.rstrip() + "\n", encoding="utf-8")

        diagram_rel_paths.append(str(dst_rel))

    # --- Git commit + push --------------------------------------------------
    try:
        # Check whether there are content changes before staging
        status_before = _git(["status", "--porcelain"], cwd=pipeline_repo_dir)
        has_content_changes = bool(status_before.strip())

        # Stage docs (architecture + diagrams)
        _git(["add", "docs/architecture", "docs/diagrams"], cwd=pipeline_repo_dir)

        # Always create a commit; allow-empty when there are no content changes
        commit_args = ["commit"]
        if not has_content_changes:
            commit_args.append("--allow-empty")
        commit_args += [
            "-m",
            f"Update architecture & diagrams for project '{slug}'",
        ]
        _git(commit_args, cwd=pipeline_repo_dir)

        changed = True

        # Try to push; if rejected because remote is ahead, auto pull + retry once
        try:
            _git(["push", "origin", "master"], cwd=pipeline_repo_dir)
        except RuntimeError as push_exc:
            msg = str(push_exc)
            if "fetch first" in msg or "non-fast-forward" in msg:
                # Bring local up to date, rebase, and retry push
                _git(["pull", "--rebase", "origin", "master"], cwd=pipeline_repo_dir)
                _git(["push", "origin", "master"], cwd=pipeline_repo_dir)
            else:
                # Different push error; surface it
                raise

        # Whether or not there were prior changes, we now have a new commit
        commit_sha = _git(["rev-parse", "HEAD"], cwd=pipeline_repo_dir)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Git operation failed: {exc}",
        )

    commit_sha_short = commit_sha[:7]
    commit_url = (
        f"https://github.com/SevDev21/disney-ai-plus/commit/{commit_sha}"
    )

    return {
        "ok": True,
        "project": slug,
        "architecture_file": str(arch_rel_path),
        "diagram_files": diagram_rel_paths,
        "changed": changed,
        "commit": commit_sha_short,
        "commit_url": commit_url,
    }


@router.post("/{slug}/pipeline")
async def send_to_pipeline(slug: str):
    """
    Export the latest architecture + diagrams for a project into the
    Disney+ pipeline repo and push a commit.

    The behavior is unchanged; this POST endpoint is what the UI already calls.
    """
    return _export_to_pipeline(slug)


@router.get("/{slug}/pipeline")
async def send_to_pipeline_get(slug: str):
    """
    GET variant of the same pipeline export, so that direct navigation to
    /api/projects/<slug>/pipeline (or tools using GET) behaves consistently.
    """
    return _export_to_pipeline(slug)
