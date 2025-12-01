# server/routers/brief.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from server.db import get_session
from server.models import Project
from server.services.files import ensure_project_tree

router = APIRouter(
    prefix="/api/projects",
    tags=["brief"],
)

DOCS_ROOT = Path("docs/projects")


class BriefPayload(BaseModel):
    brief: Dict[str, Any]


def _get_project_or_404(slug: str, session) -> Project:
    """
    Fetch a Project by slug or raise HTTP 404.
    Uses the same select(...) pattern as ui.py.
    """
    project = session.exec(
        select(Project).where(Project.slug == slug)
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return project


def _brief_path(slug: str) -> Path:
    """Return docs/projects/{slug}/brief.json."""
    return DOCS_ROOT / slug / "brief.json"


def _trigger_docs_refresh_local() -> None:
    """
    Trigger docs refresh using the same pattern as ui.py.
    This runs run_build_nav.py and restarts the docs container.
    """
    import subprocess
    import sys
    from pathlib import Path
    
    # FIXED: server/routers/brief.py -> go up 2 levels to reach arch-workbench/
    # server/routers/ -> server/ -> arch-workbench/
    REPO_ROOT = Path(__file__).resolve().parents[2]
    
    # Step 1: rebuild nav + combined project index pages
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "server.services.run_build_nav",
            ],
            cwd=str(REPO_ROOT),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("[brief.py] Successfully ran run_build_nav")
    except subprocess.CalledProcessError as e:
        print(f"[brief.py] WARNING: run_build_nav failed: {e}")
        print(f"[brief.py] STDOUT: {e.stdout.decode() if e.stdout else 'none'}")
        print(f"[brief.py] STDERR: {e.stderr.decode() if e.stderr else 'none'}")
    except Exception as e:
        print(f"[brief.py] WARNING: run_build_nav failed: {e}")
    
    # Step 2: restart docs container
    try:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "compose/docker-compose.yml",
                "restart",
                "docs",
            ],
            cwd=str(REPO_ROOT),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("[brief.py] Successfully restarted docs container")
    except subprocess.CalledProcessError as e:
        print(f"[brief.py] WARNING: docker restart docs failed: {e}")
        print(f"[brief.py] STDOUT: {e.stdout.decode() if e.stdout else 'none'}")
        print(f"[brief.py] STDERR: {e.stderr.decode() if e.stderr else 'none'}")
    except Exception as e:
        print(f"[brief.py] WARNING: docker restart docs failed: {e}")


def _create_package_scaffolds(slug: str, brief_data: Dict[str, Any]) -> None:
    """
    Create scaffold markdown files in docs/projects/<slug>/package/ based on brief.json.
    
    This generates the initial Package section content that appears on the MkDocs
    project page, even before diagrams are generated.
    """
    package_dir = DOCS_ROOT / slug / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    
    project_name = brief_data.get("project_name", slug.replace("-", " ").title())
    summary = brief_data.get("summary", "No summary provided.")
    
    # Extract actors if present
    actors = brief_data.get("actors", [])
    actors_section = ""
    if actors:
        actors_section = "\n".join(
            f"* {actor.get('name', 'Unknown')} ({actor.get('role', 'role not specified')}) — "
            f"{actor.get('description', 'No description provided.')}"
            for actor in actors
        )
    else:
        actors_section = "* User () — An individual who interacts with the system."
    
    # spec.md - Architecture Spec
    spec_content = f"""# {project_name} – Architecture Specification

## Summary

{summary}
"""
    (package_dir / "spec.md").write_text(spec_content.strip() + "\n", encoding="utf-8")
    
    # reference-arch.md - Reference Architecture  
    ref_arch_content = f"""# Reference Architecture

## Context

This section summarizes the high-level context and major actors as understood from the requirements brief.

## Actors

{actors_section}

## Key Scenarios

See generated sequence diagrams and the SRS for detailed flows.
"""
    (package_dir / "reference-arch.md").write_text(ref_arch_content.strip() + "\n", encoding="utf-8")
    
    # implementation-guide.md - Implementation Guide
    impl_content = f"""# Implementation Guide

## Overview

This guide outlines a suggested implementation path based on the requirements brief and generated architecture views.

## Next Steps

* Refine containers and components based on the C4 diagrams.
* Align implementation tasks with user journeys and requirements.
* Feed these artifacts into the downstream developer AI.
"""
    (package_dir / "implementation-guide.md").write_text(impl_content.strip() + "\n", encoding="utf-8")
    
    # srs.md - Software Requirements Specification
    srs_content = f"""# Software Requirements Specification (SRS)

## Functional Requirements

See the Architecture Spec and generated diagrams for detailed functional requirements.

## Non-Functional Requirements

* Performance: The system should respond to user requests within acceptable time limits.
* Security: All user data must be protected and authenticated properly.
* Scalability: The architecture should support growth in users and data.
"""
    (package_dir / "srs.md").write_text(srs_content.strip() + "\n", encoding="utf-8")
    
    print(f"[brief.py] Created package scaffold files for project '{slug}'")



@router.get("/{slug}/brief")
def get_brief(
    slug: str,
    session=Depends(get_session),
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    GET /api/projects/{slug}/brief

    Returns:
        { "brief": {...} }  if the file exists
        { "brief": null }   if it does not (no 404 in that case)
    """
    _get_project_or_404(slug, session)

    path = _brief_path(slug)
    if not path.exists():
        return {"brief": None}

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read brief for project '{slug}': {exc}",
        ) from exc

    return {"brief": data}


@router.post("/{slug}/brief")
def save_brief(
    slug: str,
    payload: BriefPayload,
    session=Depends(get_session),
) -> Dict[str, Any]:
    """
    POST /api/projects/{slug}/brief

    Body:
        { "brief": { ... } }

    Creates or overwrites docs/projects/{slug}/brief.json.
    """
    project = _get_project_or_404(slug, session)

    # Ensure docs tree is present for this project.
    try:
        ensure_project_tree(project.slug, project.name)
    except TypeError:
        # In case ensure_project_tree(slug) is the current signature.
        ensure_project_tree(project.slug)

    path = _brief_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        path.write_text(
            json.dumps(payload.brief, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save brief for project '{slug}': {exc}",
        ) from exc

    # Create scaffold package files so the Package section is populated
    _create_package_scaffolds(slug, payload.brief)

    # CRITICAL FIX: Trigger docs refresh so MkDocs picks up the changes
    # This mirrors the pattern used in ui.py for create/delete operations
    print(f"[brief.py] Triggering docs refresh for project '{slug}'")
    _trigger_docs_refresh_local()

    return {"status": "ok"}
