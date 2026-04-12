# server/routers/pipeline.py

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from server.db import get_session
from server.models import Setting
from server.services.run_build_nav import (
    PROJECTS_ROOT,
    DIAGRAM_FILES,
    _read_without_leading_title,
    build_pipeline_diagram_markdown,
)
from server.services.github_push import push_files_to_github, GitHubPushError

router = APIRouter(prefix="/api/projects", tags=["pipeline"])


class PipelineRequest(BaseModel):
    repo: Optional[str] = None   # "owner/repo" format
    token: Optional[str] = None  # GitHub PAT with Contents: Write permission


def _build_pipeline_files(slug: str) -> dict[str, str]:
    """
    Build all markdown file contents in memory for the pipeline export.
    Returns {repo_relative_path: file_content_string}.
    """
    project_dir = PROJECTS_ROOT / slug
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Unknown project slug")

    index_path = project_dir / "index.md"
    if not index_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Project index.md not found; generate diagrams first.",
        )

    files: dict[str, str] = {}

    # --- Architecture file: extract the Package section from index.md ---
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

    arch_body = (
        index_text[pkg_pos:diag_pos].strip()
        if diag_pos > pkg_pos
        else index_text[pkg_pos:].strip()
    )

    # Strip trailing footer lines
    arch_lines = arch_body.splitlines()
    while arch_lines and not arch_lines[-1].strip():
        arch_lines.pop()
    if arch_lines and arch_lines[-1].lstrip().startswith("_Source:"):
        arch_lines.pop()
    while arch_lines and arch_lines[-1].strip() == "---":
        arch_lines.pop()
    arch_body_clean = "\n".join(arch_lines).rstrip()

    title = slug.replace("-", " ").title()
    for line in index_text.splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            break

    arch_content = "\n".join([
        f"# Architecture \u2013 {title}",
        "",
        arch_body_clean,
        "",
        "---",
        "",
        f"_Source: generated from [ArchAiTect Workbench](https://workbench.shafie.org/projects/{slug}/)_",
        "",
    ]).rstrip() + "\n"

    files[f"docs/architecture/{slug}.md"] = arch_content

    # --- Diagram files: one markdown file per diagram type ---
    diagrams_src_root = project_dir / "diagrams"
    for section_title, filename in DIAGRAM_FILES:
        src_path = diagrams_src_root / filename
        if not src_path.exists():
            continue

        body = _read_without_leading_title(src_path)
        if not body:
            continue

        diag_lines = body.splitlines()
        while diag_lines and not diag_lines[-1].strip():
            diag_lines.pop()
        if diag_lines and diag_lines[-1].lstrip().startswith("_Source:"):
            diag_lines.pop()
        while diag_lines and diag_lines[-1].strip() == "---":
            diag_lines.pop()
        body_clean = "\n".join(diag_lines).rstrip()
        if not body_clean:
            continue

        rendered = build_pipeline_diagram_markdown(
            body_clean, section_title, slug, image_rel_path=None,
        )
        files[f"docs/diagrams/{slug}/{filename}"] = rendered.rstrip() + "\n"

    return files


async def _do_pipeline(slug: str, req: PipelineRequest, session) -> dict:
    """Core pipeline logic: resolve config, build files, push to GitHub."""
    repo = req.repo
    token = req.token

    # Fall back to stored per-project config if not provided in the request
    if not repo or not token:
        repo_s = session.exec(
            select(Setting).where(Setting.key == f"project:{slug}:github_repo")
        ).first()
        tok_s = session.exec(
            select(Setting).where(Setting.key == f"project:{slug}:github_token")
        ).first()
        if not repo:
            repo = repo_s.value if repo_s else None
        if not token:
            token = tok_s.value if tok_s else None

    if not repo or not token:
        raise HTTPException(
            status_code=400,
            detail=(
                "No GitHub repository configured for this project. "
                "Provide 'repo' (owner/repo) and 'token' in the request body."
            ),
        )

    if "/" not in repo:
        raise HTTPException(
            status_code=400,
            detail="repo must be in 'owner/repo' format (e.g. NimaShafie/test-repo)",
        )

    # Persist config so future calls can omit repo/token
    for key, val in [
        (f"project:{slug}:github_repo", repo),
        (f"project:{slug}:github_token", token),
    ]:
        s = session.exec(select(Setting).where(Setting.key == key)).first()
        if s:
            s.value = val
        else:
            session.add(Setting(key=key, value=val))
    session.commit()

    # Build all file contents in memory
    files = _build_pipeline_files(slug)

    # Push to GitHub via API (no local git required)
    owner, repo_name = repo.split("/", 1)
    try:
        result = push_files_to_github(
            owner=owner,
            repo=repo_name,
            token=token,
            files=files,
            message=f"Update architecture & diagrams for project '{slug}'",
        )
    except GitHubPushError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "ok": True,
        "project": slug,
        "files_pushed": result["files_pushed"],
        "commit": result["commit_sha_short"],
        "commit_url": result["commit_url"],
        "repo_url": result["repo_url"],
        "repo_tree_url": result["repo_tree_url"],
        "branch": result["branch"],
    }


@router.post("/{slug}/pipeline")
async def send_to_pipeline(
    slug: str,
    req: Optional[PipelineRequest] = Body(default=None),
    session=Depends(get_session),
):
    """
    Export the latest architecture + diagrams for a project to a GitHub
    repository via the GitHub API.

    Accepts optional JSON body:
        { "repo": "owner/repo", "token": "ghp_..." }

    If omitted, falls back to the per-project stored configuration.
    The provided repo/token are saved for future calls.
    """
    return await _do_pipeline(slug, req or PipelineRequest(), session)


@router.get("/{slug}/pipeline")
async def send_to_pipeline_get(slug: str, session=Depends(get_session)):
    """
    GET variant — uses stored per-project GitHub config only.
    Useful for testing or direct browser navigation.
    """
    return await _do_pipeline(slug, PipelineRequest(), session)
