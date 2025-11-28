# server/routers/generate.py

from typing import List, Optional
from pathlib import Path
import json
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.schemas import DiagramChoices
from server.services.orchestrator import generate_all, _diagram_stub_puml
from server.services.pipeline_export import run_export_pipeline, PipelineError

router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    # Matches payload from ui_project.html: { "diagrams": ["c4_context", ...] }
    diagrams: List[str]


class GenerateResponse(BaseModel):
    status: str
    diagrams: List[str]


def _to_diagram_choices(ids: List[str]) -> DiagramChoices:
    """
    Map the string IDs from the UI into the existing DiagramChoices schema.
    Any diagram not listed in `ids` is treated as False.
    """
    return DiagramChoices(
        c4_context="c4_context" in ids,
        c4_container="c4_container" in ids,
        c4_component="c4_component" in ids,
        sequence="sequence" in ids,
        deployment="deployment" in ids,
        logical="logical" in ids,
    )


# Human-friendly titles for each diagram page
_DIAGRAM_TITLES = {
    "c4_context": "C4 Context",
    "c4_container": "C4 Container",
    "c4_component": "C4 Component",
    "sequence": "Sequence",
    "deployment": "Deployment",
    "logical": "Logical",
}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ensure_diagram_pages(slug: str, ids: List[str]) -> None:
    """
    Ensure that each selected diagram has a corresponding Markdown page under:
      docs/projects/<slug>/diagrams/<diagram_id>.md

    These pages are what MkDocs serves at:
      /projects/<slug>/diagrams/<diagram_id>/

    We generate simple PlantUML stubs using _diagram_stub_puml so that the
    Kroki / PlantUML toolchain can render something useful immediately.
    """
    # Repo root: .../arch-workbench
    root = Path(__file__).resolve().parents[2]
    project_dir = root / "docs" / "projects" / slug
    diagrams_dir = project_dir / "diagrams"

    diagrams_dir.mkdir(parents=True, exist_ok=True)

    # Try to load brief to get project_name + summary (optional).
    brief: dict = {}
    project_name = slug
    brief_path = project_dir / "brief.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            project_name = (brief.get("project_name") or slug).strip() or slug
        except Exception:
            # Don't let brief parsing kill generation – fall back to slug.
            brief = {}

    for diagram_id in ids:
        title = _DIAGRAM_TITLES.get(diagram_id)
        if not title:
            # Ignore unknown diagram IDs quietly
            continue

        md_path = diagrams_dir / f"{diagram_id}.md"

        # Always overwrite for now so re-generation refreshes content.
        try:
            plantuml_src = _diagram_stub_puml(diagram_id, project_name, brief)
        except Exception:
            # If for some reason stub generation fails, still create a
            # placeholder markdown page so the URL is not 404.
            content = (
                f"# {title}\n\n"
                f"Diagram placeholder for **{project_name}**.\n\n"
                "_An error occurred while generating the PlantUML stub._\n"
            )
            _write_text(md_path, content)
            continue

        content = (
            f"# {title}\n\n"
            f"Generated diagram stub for **{project_name}**.\n\n"
            "```plantuml\n"
            f"{plantuml_src}\n"
            "```\n"
        )
        _write_text(md_path, content)


@router.post("/api/projects/{slug}/generate", response_model=GenerateResponse)
async def generate_project(slug: str, body: GenerateRequest) -> GenerateResponse:
    """
    Trigger diagram + docs generation for a project slug.

    The UI sends a list of diagram IDs; we convert that into DiagramChoices
    and hand off to generate_all, which handles PlantUML/Kroki + MkDocs.
    Then we ensure that per-diagram Markdown pages exist so that MkDocs
    routes like /projects/<slug>/diagrams/c4_context/ are not 404.
    """
    if not body.diagrams:
        raise HTTPException(status_code=400, detail="No diagram types provided")

    choices_model = _to_diagram_choices(body.diagrams)

    try:
        # Primary: new signature generate_all(slug, diagram_choices)
        try:
            generate_all(slug, choices_model)
        except TypeError:
            # Fallback: older signature generate_all(slug)
            generate_all(slug)

        # Ensure MkDocs diagram pages exist for the selected diagram IDs
        _ensure_diagram_pages(slug, body.diagrams)

    except Exception as exc:
        # Surface as clean JSON error for the UI toast
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {exc}",
        ) from exc

    return GenerateResponse(status="ok", diagrams=body.diagrams)


# ---------------------------------------------------------------------------
# Pipeline endpoint: export generated docs/diagrams into external Git repo
# ---------------------------------------------------------------------------

GITHUB_REPO_HTTP = "https://github.com/SevDev21/disney-ai-plus"
REPO_ROOT_ENV_VAR = "ARCH_PIPELINE_REPO_ROOT"


def _get_export_repo_root() -> Path:
    """
    Resolve the local clone of the export repo.

    Set ARCH_PIPELINE_REPO_ROOT in the arch-api systemd unit, e.g.:

      Environment=ARCH_PIPELINE_REPO_ROOT=/opt/disney-ai-plus
    """
    raw = os.environ.get(REPO_ROOT_ENV_VAR)
    if not raw:
        raise HTTPException(
            status_code=500,
            detail=(
                f"{REPO_ROOT_ENV_VAR} is not set; configure it to point to the "
                "local disney-ai-plus repo on the server."
            ),
        )
    root = Path(raw).expanduser().resolve()
    if not root.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Export repo path does not exist: {root}",
        )
    return root


def _build_commit_url(commit_hash: Optional[str]) -> Optional[str]:
    if not commit_hash:
        return None
    return f"{GITHUB_REPO_HTTP}/commit/{commit_hash}"


@router.post("/api/projects/{slug}/pipeline")
async def trigger_pipeline(slug: str):
    """
    Trigger the export pipeline for a project.

    This calls server.services.pipeline_export.run_export_pipeline, which:
      - updates a small per-project pipeline log (so there is always a change),
      - stages architecture + diagram files + the log,
      - always creates a commit (empty if needed),
      - pushes to the configured remote.

    The JSON shape is consumed by the MkDocs UI modal.
    """
    repo_root = _get_export_repo_root()

    try:
        result = run_export_pipeline(
            project_slug=slug,
            repo_root=repo_root,
        )
    except PipelineError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {exc}",
        ) from exc

    # Convert commit hash into a full GitHub URL
    result["commit_url"] = _build_commit_url(result.get("commit"))

    return result
