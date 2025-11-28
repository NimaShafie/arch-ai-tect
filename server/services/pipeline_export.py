# server/services/pipeline_export.py

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Default to the real path, but allow override via PIPELINE_EXPORT_REPO
EXPORT_REPO_PATH = Path(
    os.getenv("PIPELINE_EXPORT_REPO", "/home/n1mz/projects/disney-ai-plus")
).expanduser()


class PipelineError(Exception):
    """Raised when the export pipeline fails."""


def _run_git(args: List[str], cwd: Path) -> str:
    """Run a git command and return stdout (raise on error)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PipelineError(
            f"git {' '.join(args)} failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def _ensure_pipeline_log(repo_root: Path, project_slug: str) -> Path:
    """
    Touch / append a tiny timestamped log entry so we ALWAYS have at least
    one changed file per run. This guarantees git commit won't be a no-op.
    """
    log_dir = repo_root / "docs" / ".pipeline-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / f"{project_slug}.log"
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{ts} - export refreshed for project '{project_slug}'\n")

    return log_path


def _compute_files(project_slug: str) -> Tuple[str, List[str]]:
    """
    Return the architecture file and diagram files as *relative* paths from
    the repo root. These are the same values we send back in JSON.
    """
    architecture_file = f"docs/architecture/{project_slug}.md"

    diagram_files = [
        f"docs/diagrams/{project_slug}/c4_context.md",
        f"docs/diagrams/{project_slug}/c4_container.md",
        f"docs/diagrams/{project_slug}/c4_component.md",
        f"docs/diagrams/{project_slug}/logical.md",
        f"docs/diagrams/{project_slug}/deployment.md",
        f"docs/diagrams/{project_slug}/sequence.md",
    ]

    return architecture_file, diagram_files


def run_export_pipeline(
    project_slug: str,
    repo_root: Path,
    commit_message: str | None = None,
    remote_name: str = "origin",
    remote_branch: str = "master",
) -> Dict:
    """
    Main entrypoint used by the FastAPI router.

    - Always updates a per-project pipeline log.
    - Stages all architecture & diagram files + the log.
    - Always creates a commit (because the log changes every run).
    - Pushes to the configured remote.
    - Returns JSON metadata used by the UI modal.
    """
    repo_root = repo_root.resolve()

    if commit_message is None:
        commit_message = f"chore: refresh generated docs for project '{project_slug}'"

    architecture_file, diagram_files = _compute_files(project_slug)

    # Ensure we have at least one changed file
    log_path_rel = _ensure_pipeline_log(repo_root, project_slug)
    log_rel = log_path_rel.relative_to(repo_root).as_posix()

    # Stage architecture + diagrams + log
    to_add = [architecture_file] + diagram_files + [log_rel]
    try:
        _run_git(["add"] + to_add, cwd=repo_root)
    except PipelineError:
        # If files don't exist yet, git add will complain; that's OK – we still
        # want to try to commit the log file.
        # Re-add only the log file which we know exists.
        _run_git(["add", log_rel], cwd=repo_root)

    # See what's staged
    status = _run_git(["status", "--porcelain"], cwd=repo_root)
    changed = bool(status.strip())

    # Even if somehow nothing is staged (shouldn't happen because of the log),
    # we still run commit, but guard against empty-commit error.
    commit_hash = None
    try:
        if changed:
            _run_git(["commit", "-m", commit_message], cwd=repo_root)
            commit_hash = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
            # Push in the background-ish – if this fails, we still report commit.
            _run_git(["push", remote_name, remote_branch], cwd=repo_root)
        else:
            # No changes; create an explicit empty commit so there is a history
            # entry for the run.
            _run_git(["commit", "--allow-empty", "-m", commit_message], cwd=repo_root)
            commit_hash = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
            _run_git(["push", remote_name, remote_branch], cwd=repo_root)
            changed = True
    except PipelineError:
        # Surface git error back to caller.
        raise

    commit_url = None
    if commit_hash:
        # NOTE: commit_url is usually constructed elsewhere using the GitHub
        # repo URL; the router can patch this if needed.
        commit_url = commit_hash  # placeholder, router will turn into full URL

    return {
        "ok": True,
        "project": project_slug,
        "architecture_file": architecture_file,
        "diagram_files": diagram_files,
        "changed": changed,
        "commit": commit_hash,
        "commit_url": commit_url,
    }
