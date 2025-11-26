# server/services/orchestrator.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from .files import ensure_project_tree, write_yaml

# Map of diagram type -> (filename, syntax, extension)
DIAGRAM_META: Dict[str, Tuple[str, str, str]] = {
    "c4_context":   ("c4-context.puml",   "plantuml", ".puml"),
    "c4_container": ("c4-container.puml", "plantuml", ".puml"),
    "c4_component": ("c4-component.puml", "plantuml", ".puml"),
    "sequence":     ("sequence.puml",    "plantuml", ".puml"),
    "deployment":   ("deployment.puml",  "plantuml", ".puml"),
    "logical":      ("logical.puml",     "plantuml", ".puml"),
}


def _load_brief(project_dir: Path) -> dict:
    brief_path = project_dir / "brief.json"
    if not brief_path.exists():
        raise RuntimeError(f"brief.json not found for project at {brief_path}")
    try:
        return json.loads(brief_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to parse brief.json: {e}")


def _project_name_from_brief(brief: dict, slug: str) -> str:
    return (brief.get("project_name") or slug).strip() or slug


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# -----------------------------------------------------------------------------#
# Package docs
# -----------------------------------------------------------------------------#

def _md_header(title: str) -> str:
    return f"# {title}\n\n"


def _md_section(title: str, body: str) -> str:
    if not body.strip():
        return ""
    return f"## {title}\n\n{body.strip()}\n\n"


def _summarize_brief(brief: dict) -> str:
    summary = brief.get("summary") or ""
    domain = brief.get("domain") or ""
    lines = []
    if summary:
        lines.append(summary.strip())
    if domain:
        lines.append(f"**Domain:** {domain}")
    return "\n\n".join(lines)


def _md_list(items) -> str:
    if not items:
        return ""
    return "\n".join(f"- {i}" for i in items if str(i).strip()) + "\n\n"


def _package_spec(project_name: str, brief: dict) -> str:
    parts = [_md_header(f"{project_name} – Architecture Specification")]

    parts.append(_md_section("Summary", _summarize_brief(brief)))

    stakeholders = brief.get("stakeholders") or []
    if stakeholders:
        lines = []
        for s in stakeholders:
            name = s.get("name") or "Unknown"
            role = s.get("role") or ""
            concerns = s.get("concerns") or []
            c_str = ", ".join(concerns) if concerns else ""
            line = f"- **{name}** ({role})"
            if c_str:
                line += f" — concerns: {c_str}"
            lines.append(line)
        parts.append(_md_section("Stakeholders", "\n".join(lines)))

    frs = brief.get("functional_requirements") or []
    if frs:
        lines = []
        for fr in frs:
            fid = fr.get("id") or ""
            title = fr.get("title") or ""
            desc = fr.get("description") or ""
            hdr = f"**{fid}** – {title}".strip(" –")
            lines.append(f"- {hdr}")
            if desc:
                lines.append(f"  - {desc}")
        parts.append(_md_section("Functional Requirements", "\n".join(lines)))

    return "".join(parts)


def _package_srs(project_name: str, brief: dict) -> str:
    parts = [_md_header(f"{project_name} – Software Requirements Specification")]

    parts.append(_md_section("Summary", _summarize_brief(brief)))

    journeys = brief.get("user_journeys") or []
    if journeys:
        lines = []
        for j in journeys:
            jid = j.get("id") or ""
            name = j.get("name") or ""
            desc = j.get("description") or ""
            steps = j.get("steps") or []
            header = f"**{jid}** – {name}".strip(" –")
            lines.append(header)
            if desc:
                lines.append(f"  - {desc}")
            if steps:
                for s in steps:
                    lines.append(f"    - {s}")
        parts.append(_md_section("User Journeys", "\n".join(lines)))

    nfr = brief.get("non_functional_requirements") or {}
    if nfr:
        lines = []
        for k, v in nfr.items():
            if not v:
                continue
            lines.append(f"### {k.replace('_', ' ').title()}")
            for item in v:
                lines.append(f"- {item}")
            lines.append("")
        parts.append(_md_section("Non-Functional Requirements", "\n".join(lines)))

    return "".join(parts)


def _package_reference_arch(project_name: str, brief: dict) -> str:
    parts = [_md_header(f"{project_name} – Reference Architecture")]

    parts.append(
        _md_section(
            "Context",
            "This section summarizes the high-level context and major actors "
            "as understood from the requirements brief."
        )
    )

    actors = brief.get("actors") or []
    if actors:
        lines = []
        for a in actors:
            name = a.get("name") or "Unknown"
            typ = a.get("type") or ""
            desc = a.get("description") or ""
            line = f"- **{name}** ({typ})"
            if desc:
                line += f" — {desc}"
            lines.append(line)
        parts.append(_md_section("Actors", "\n".join(lines)))

    parts.append(
        _md_section(
            "Key Scenarios",
            "See generated sequence diagrams and the SRS for detailed flows."
        )
    )

    return "".join(parts)


def _package_impl_guide(project_name: str, brief: dict) -> str:
    parts = [_md_header(f"{project_name} – Implementation Guide")]

    parts.append(
        _md_section(
            "Overview",
            "This guide outlines a suggested implementation path based on the "
            "requirements brief and generated architecture views."
        )
    )

    constraints = brief.get("constraints") or []
    if constraints:
        lines = []
        for c in constraints:
            typ = c.get("type") or "constraint"
            desc = c.get("description") or ""
            lines.append(f"- **{typ.title()}** – {desc}")
        parts.append(_md_section("Constraints", "\n".join(lines)))

    tech = brief.get("technical_preferences") or {}
    if tech:
        lines = []
        for k, v in tech.items():
            if not v:
                continue
            lines.append(f"### {k.replace('_', ' ').title()}")
            for item in v:
                lines.append(f"- {item}")
            lines.append("")
        parts.append(_md_section("Technical Preferences", "\n".join(lines)))

    parts.append(
        _md_section(
            "Next Steps",
            "- Refine containers and components based on the C4 diagrams.\n"
            "- Align implementation tasks with user journeys and requirements.\n"
            "- Feed these artifacts into the downstream developer AI."
        )
    )

    return "".join(parts)


# -----------------------------------------------------------------------------#
# Diagram stubs
# -----------------------------------------------------------------------------#

def _diagram_stub_puml(diagram_type: str, project_name: str, brief: dict) -> str:
    """
    Produce a simple PlantUML stub for the given diagram type.
    These are intentionally minimal and serve as starting points.
    """
    summary = brief.get("summary") or ""
    header = f"'{project_name} – {diagram_type} diagram stub\n"
    if summary:
        header += f"'{summary}\n"

    if diagram_type == "c4_context":
        body = (
            "@startuml\n"
            "!include <C4/C4_Container>\n\n"
            "title System Context\n\n"
            "Person(user, \"User\")\n"
            "System(system, \"System\", \"High-level description\")\n"
            "Rel(user, system, \"Uses\")\n\n"
            "@enduml\n"
        )
    elif diagram_type == "c4_container":
        body = (
            "@startuml\n"
            "!include <C4/C4_Container>\n\n"
            "title Container View\n\n"
            "System_Boundary(system, \"System\") {\n"
            "  Container(web, \"Web App\", \"Browser\", \"Allows users to interact\")\n"
            "  Container(api, \"API\", \"HTTP\", \"Business logic\")\n"
            "  Container(db, \"Database\", \"SQL/NoSQL\", \"Stores data\")\n"
            "}\n"
            "Rel(web, api, \"Uses\")\n"
            "Rel(api, db, \"Reads/Writes\")\n\n"
            "@enduml\n"
        )
    elif diagram_type == "c4_component":
        body = (
            "@startuml\n"
            "!include <C4/C4_Component>\n\n"
            "title Component View (API)\n\n"
            "Container(api, \"API\", \"HTTP\") {\n"
            "  Component(auth, \"Auth Component\", \"Handles authentication\")\n"
            "  Component(catalog, \"Catalog Component\", \"Catalog operations\")\n"
            "}\n\n"
            "@enduml\n"
        )
    elif diagram_type == "sequence":
        body = (
            "@startuml\n"
            "title Example Sequence (Login)\n\n"
            "actor User\n"
            "participant WebApp\n"
            "participant API\n"
            "participant IdentityProvider\n\n"
            "User -> WebApp: Enter credentials\n"
            "WebApp -> API: POST /login\n"
            "API -> IdentityProvider: Verify credentials\n"
            "IdentityProvider --> API: Result\n"
            "API --> WebApp: Session / token\n"
            "WebApp --> User: Logged in\n\n"
            "@enduml\n"
        )
    elif diagram_type == "deployment":
        body = (
            "@startuml\n"
            "title Deployment Diagram (Simplified)\n\n"
            "node \"Cloud Region\" {\n"
            "  node \"Kubernetes Cluster\" {\n"
            "    node \"API Pod\" as api\n"
            "    node \"Web Pod\" as web\n"
            "  }\n"
            "  database db\n"
            "}\n\n"
            "@enduml\n"
        )
    elif diagram_type == "logical":
        body = (
            "@startuml\n"
            "title Logical / Domain View\n\n"
            "class User {\n"
            "  +id\n"
            "  +email\n"
            "}\n\n"
            "class Subscription {\n"
            "  +id\n"
            "  +status\n"
            "}\n\n"
            "User \"1\" -- \"*\" Subscription\n\n"
            "@enduml\n"
        )
    else:
        body = (
            "@startuml\n"
            "title Generic Diagram Stub\n\n"
            "note as N1\n"
            "  TODO: Replace this stub with a concrete diagram\n"
            "  for the requested type.\n"
            "end note\n\n"
            "@enduml\n"
        )

    return header + "\n" + body


def _emit_diagram(project_dir: Path, project_name: str, brief: dict, key: str) -> None:
    if key not in DIAGRAM_META:
        return
    filename, syntax, ext = DIAGRAM_META[key]
    src_dir = project_dir / "diagrams" / "src"
    path = src_dir / filename
    text = _diagram_stub_puml(key, project_name, brief)
    _write_text(path, text)


# -----------------------------------------------------------------------------#
# Public API
# -----------------------------------------------------------------------------#

def generate_all(slug: str, selected: List[str] | None = None) -> Path:
    """
    Generate package docs, diagram stubs, and manifest.yaml for a project.

    :param slug: project slug
    :param selected: list of diagram types to emit (keys of DIAGRAM_META)
    :return: Path to the project docs directory (docs/projects/<slug>)
    """
    project_dir = ensure_project_tree(slug)
    brief = _load_brief(project_dir)
    project_name = _project_name_from_brief(brief, slug)

    # Main project index
    index_md = [
        f"# {project_name}\n",
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
        "- Diagrams are available under the `diagrams/` section of the docs.",
        "",
    ]
    _write_text(project_dir / "index.md", "\n".join(index_md) + "\n")

    # Package docs
    _write_text(project_dir / "package" / "spec.md", _package_spec(project_name, brief))
    _write_text(project_dir / "package" / "srs.md", _package_srs(project_name, brief))
    _write_text(
        project_dir / "package" / "reference-arch.md",
        _package_reference_arch(project_name, brief),
    )
    _write_text(
        project_dir / "package" / "implementation-guide.md",
        _package_impl_guide(project_name, brief),
    )

    # Diagrams
    selected = selected or []
    for key in selected:
        _emit_diagram(project_dir, project_name, brief, key)

    # Manifest
    manifest = {
        "name": project_name,
        "slug": slug,
        "nav_title": project_name,
        "choices": selected,
        "files": [
            {"path": f"projects/{slug}/index.md", "kind": "doc"},
            {"path": f"projects/{slug}/package/spec.md", "kind": "doc"},
            {"path": f"projects/{slug}/package/srs.md", "kind": "doc"},
            {"path": f"projects/{slug}/package/reference-arch.md", "kind": "doc"},
            {"path": f"projects/{slug}/package/implementation-guide.md", "kind": "doc"},
        ],
    }
    write_yaml(project_dir / "manifest.yaml", manifest)

    return project_dir
