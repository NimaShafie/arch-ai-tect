# server/services/refresh_docs.py

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_build_nav() -> None:
    """
    Run the project nav + index builder on the host:

        python -m server.services.run_build_nav

    This regenerates:
      - docs/projects/index.md
      - docs/projects/<slug>/index.md
      - mkdocs.yml nav
      - any helper YAML, etc.
    """
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "server.services.run_build_nav",
            ],
            cwd=str(REPO_ROOT),
            check=True,
        )
    except Exception as exc:
        # Soft-fail: we log to stderr but don't blow up the API request
        print(f"[refresh_docs] WARNING: run_build_nav failed: {exc}", file=sys.stderr)


def _restart_docs_container() -> None:
    """
    Best-effort restart of the MkDocs 'docs' container so that any
    changes on disk are picked up even if dirtyreload misses them.
    """
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
        )
    except Exception as exc:
        # Don't kill the request if Docker isn't available
        print(f"[refresh_docs] WARNING: docker restart docs failed: {exc}", file=sys.stderr)


def refresh_docs_container(slug: Optional[str] = None) -> None:
    """
    Public entry point used by the routers.

    slug is currently ignored (we always rebuild the full nav + indexes),
    but we keep it in the signature so you can later optimize to only
    touch a single project if you want.

    Called from:
      - brief.py  (after saving brief)
      - generate.py (after generating diagrams)
      - ui.py (after create/delete project)
    """
    _run_build_nav()
    _restart_docs_container()
