# server/routers/pipeline.py

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/projects", tags=["pipeline"])

# Where the docs live in THIS repo
DOCS_ROOT = Path("docs") / "projects"


def _run_git(args: List[str], cwd: Path) -> None:
    """Run a git command in the pipeline repo; raise HTTPException on failure."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run git command {args}: {e}",
        )

    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=(
                f"git {' '.join(args)} failed with code {proc.returncode}: "
                f"{proc.stderr.strip()}"
            ),
        )


def _get_pipeline_repo_dir() -> Path:
    """Resolve and validate PIPELINE_REPO_DIR."""
    repo_dir = os.getenv("PIPELINE_REPO_DIR")
    if not repo_dir:
        raise HTTPException(
            status_code=500,
            detail="PIPELINE_REPO_DIR environment variable is not set.",
        )
    path = Path(repo_dir)
    if not path.exists() or not path.is_dir():
        raise HTTPException(
            status_code=500,
            detail=f"PIPELINE_REPO_DIR '{repo_dir}' does not exist or is not a directory.",
        )
    return path


def _split_arch_vs_diagrams(index_md: str) -> Dict[str, str]:
    """
    Split a project index.md into:
      - 'architecture': everything before '### Diagrams'
      - 'diagrams': everything from '### Diagrams' onward

    If '### Diagrams' is not present, the whole file is treated as architecture.
    """
    marker = "### Diagrams"
    idx = index_md.find(marker)
    if idx == -1:
        return {"architecture": index_md, "diagrams": ""}

    arch_part = index_md[:idx].rstrip()
    diag_part = index_md[idx:].lstrip()
    return {"architecture": arch_part, "diagrams": diag_part}


@router.post("/{slug}/pipeline")
def send_project_to_pipeline(slug: str) -> Dict[str, object]:
    """
    Export the project's docs + diagrams into the external pipeline repo and push.

    - Architecture bundle:
        docs/projects/<slug>/index.md (up to '### Diagrams')
        -> PIPELINE_REPO/docs/architecture/<slug>.md

    - Diagrams:
        docs/projects/<slug>/diagrams/*.md
        -> PIPELINE_REPO/docs/diagrams/<slug>/<diagram_name>.md

    Existing files are ALWAYS overwritten.
    """
    # 1) Validate docs in this repo
    project_dir = DOCS_ROOT / slug
    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project docs not found at {project_dir}",
        )

    index_path = project_dir / "index.md"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project index.md not found at {index_path}",
        )

    diagrams_dir = project_dir / "diagrams"
    if not diagrams_dir.exists():
        diagrams_dir = None

    # 2) Read + split index.md
    index_text = index_path.read_text(encoding="utf-8")
    parts = _split_arch_vs_diagrams(index_text)
    arch_text = parts["architecture"]

    # 3) Resolve pipeline repo
    repo_dir = _get_pipeline_repo_dir()

    arch_out_dir = repo_dir / "docs" / "architecture"
    arch_out_dir.mkdir(parents=True, exist_ok=True)
    arch_out_path = arch_out_dir / f"{slug}.md"
    arch_out_path.write_text(arch_text.rstrip() + "\n", encoding="utf-8")

    written_arch_files = [str(arch_out_path.relative_to(repo_dir))]

    # 4) Export diagrams (each .md becomes its own file under docs/diagrams/<slug>/)
    written_diagram_files: List[str] = []
    if diagrams_dir and diagrams_dir.exists():
        diag_out_root = repo_dir / "docs" / "diagrams" / slug
        diag_out_root.mkdir(parents=True, exist_ok=True)

        for src in sorted(diagrams_dir.glob("*.md")):
            dest = diag_out_root / src.name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            written_diagram_files.append(str(dest.relative_to(repo_dir)))

    # 5) git add / commit / push
    #    We add the specific paths we touched.
    paths_to_add = written_arch_files + written_diagram_files
    _run_git(["add", *paths_to_add], cwd=repo_dir)

    # Only commit if there are staged changes
    status_proc = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(repo_dir),
    )
    if status_proc.returncode != 0:  # there are staged changes
        _run_git(
            ["commit", "-m", f"Update architecture & diagrams for project '{slug}'"],
            cwd=repo_dir,
        )
        _run_git(["push"], cwd=repo_dir)

    return {
        "ok": True,
        "project": slug,
        "architecture_file": written_arch_files[0],
        "diagram_files": written_diagram_files,
    }
