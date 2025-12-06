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
# Diagram stubs - ENHANCED to use brief data
# -----------------------------------------------------------------------------#
def _diagram_stub_puml(diagram_type: str, project_name: str, brief: dict) -> str:
    """
    Produce PlantUML diagrams based on actual brief content.
    Extracts actors, flows, components from the brief instead of using hardcoded stubs.
    
    ENHANCED: Now uses brief.actors[], brief.primary_flows[], and brief.technical_preferences{}
    to generate diagrams that match the actual project requirements.
    """
    summary = brief.get("summary", "")
    actors = brief.get("actors", [])
    primary_flows = brief.get("primary_flows", [])
    technical_prefs = brief.get("technical_preferences", {})
    
    # Helper: Get actors by type
    def get_actors_by_type(actor_type):
        return [a for a in actors if a.get("type") == actor_type]
    
    # Helper: Get actor name by index or fallback
    def get_actor_name(index, fallback="User"):
        return actors[index].get("name", fallback) if index < len(actors) else fallback
    
    # Helper: Sanitize name for PlantUML variable
    def sanitize_name(name):
        return name.replace(" ", "").replace("-", "").replace("/", "").lower()
    
    header = f"'{project_name} – {diagram_type}\n"
    if summary:
        header += f"'{summary}\n"
    
    if diagram_type == "c4_context":
        # Extract person actors and external services from brief
        person_actors = get_actors_by_type("person")
        system_actors = get_actors_by_type("system")
        external_actors = get_actors_by_type("external_service")
        
        # Build C4 Context from actual brief data
        lines = [
            "@startuml",
            "!include <C4/C4_Context>",
            "",
            "title System Context",
            "",
        ]
        
        # Add person actors
        if person_actors:
            for actor in person_actors[:3]:  # Limit to 3 for clarity
                name = actor.get("name", "User")
                desc = actor.get("description", "")
                var_name = sanitize_name(name)
                lines.append(f'Person({var_name}, "{name}", "{desc}")')
        else:
            lines.append('Person(user, "User", "Individual who interacts with the system")')
        
        lines.append("")
        
        # Add main system
        system_desc = summary or "High-level description"
        lines.append(f'System(system, "{project_name}", "{system_desc}")')
        
        lines.append("")
        
        # Add external systems
        if external_actors:
            for ext in external_actors[:3]:  # Limit to 3
                name = ext.get("name", "External Service")
                desc = ext.get("description", "")
                var_name = sanitize_name(name)
                lines.append(f'System_Ext({var_name}, "{name}", "{desc}")')
            lines.append("")
        
        # Add relationships
        if person_actors:
            first_person = sanitize_name(person_actors[0].get("name", "User"))
            lines.append(f'Rel({first_person}, system, "Uses")')
        else:
            lines.append('Rel(user, system, "Uses")')
        
        if external_actors:
            for ext in external_actors[:3]:
                var_name = sanitize_name(ext.get("name", ""))
                lines.append(f'Rel(system, {var_name}, "Integrates with")')
        
        lines.extend(["", "@enduml"])
        return "\n".join(lines)
    
    elif diagram_type == "c4_container":
        # Build containers from technical preferences
        frontend = technical_prefs.get("frontend", ["Web App"])[0] if technical_prefs.get("frontend") else "Web App"
        backend = technical_prefs.get("backend", ["API"])[0] if technical_prefs.get("backend") else "API"
        storage = technical_prefs.get("data_storage", ["Database"])[0] if technical_prefs.get("data_storage") else "Database"
        
        lines = [
            "@startuml",
            "!include <C4/C4_Container>",
            "",
            "title Container View",
            "",
            f'System_Boundary(system, "{project_name}") {{',
            f'  Container(web, "Web App", "Browser", "Allows users to interact")',
            f'  Container(api, "API", "HTTP", "Business logic")',
            f'  Container(db, "Database", "SQL/NoSQL", "Stores data")',
            "}",
            "",
            'Rel(web, api, "Uses")',
            'Rel(api, db, "Reads/Writes")',
            "",
            "@enduml",
        ]
        return "\n".join(lines)
    
    elif diagram_type == "c4_component":
        # Extract component names from primary flows or use defaults
        components = []
        if primary_flows:
            for flow in primary_flows[:3]:  # Use first 3 flows
                flow_name = flow.get("name", "")
                if flow_name:
                    # Extract key noun from flow name (e.g., "Video Metadata Display" → "Metadata")
                    words = flow_name.split()
                    for word in words:
                        if word.lower() not in ["display", "view", "show", "handle", "manage"]:
                            components.append(f"{word} Component")
                            break
        
        if not components:
            components = ["Auth Component", "Catalog Component"]
        
        lines = [
            "@startuml",
            "!include <C4/C4_Component>",
            "",
            "title Component View (API)",
            "",
            'Container(api, "API", "HTTP") {',
        ]
        
        for comp in components[:3]:  # Limit to 3
            var_name = sanitize_name(comp)
            desc = f"Handles {comp.lower().replace(' component', '')} operations"
            lines.append(f'  Component({var_name}, "{comp}", "{desc}")')
        
        lines.extend(["}",  "", "@enduml"])
        return "\n".join(lines)
    
    elif diagram_type == "sequence":
        # Build sequence from first primary flow
        if primary_flows:
            flow = primary_flows[0]
            flow_name = flow.get("name", "Example Sequence")
            steps = flow.get("steps", [])
            
            # Extract participants from actors
            person = get_actor_name(0, "User")
            webapp = "WebApp"
            api = "API"
            
            # Check if there are external services
            external = None
            external_actors = get_actors_by_type("external_service")
            if external_actors:
                external = external_actors[0].get("name", "").replace(" ", "")
            
            lines = [
                "@startuml",
                f"title {flow_name}",
                "",
                f"actor {person}",
                f"participant {webapp}",
                f"participant {api}",
            ]
            
            if external:
                lines.append(f"participant {external}")
            
            lines.append("")
            
            # Generate interactions from steps
            for i, step in enumerate(steps[:6]):  # Limit to 6 steps
                if i == 0:
                    lines.append(f'{person} -> {webapp}: {step}')
                elif i == 1:
                    lines.append(f'{webapp} -> {api}: {step}')
                elif i == 2 and external:
                    lines.append(f'{api} -> {external}: {step}')
                    lines.append(f'{external} --> {api}: Result')
                elif i == 3:
                    lines.append(f'{api} --> {webapp}: {step}')
                elif i == 4:
                    lines.append(f'{webapp} --> {person}: {step}')
                else:
                    lines.append(f'{api} --> {webapp}: {step}')
            
            # Add completion if not already covered
            if len(steps) > 0 and not any("complete" in s.lower() or "logged in" in s.lower() for s in steps):
                lines.append(f'{webapp} --> {person}: Complete')
            
            lines.extend(["", "@enduml"])
            return "\n".join(lines)
        else:
            # Fallback to generic login
            lines = [
                "@startuml",
                "title Example Sequence (Login)",
                "",
                "actor User",
                "participant WebApp",
                "participant API",
                "participant IdentityProvider",
                "",
                "User -> WebApp: Enter credentials",
                "WebApp -> API: POST /login",
                "API -> IdentityProvider: Verify credentials",
                "IdentityProvider --> API: Result",
                "API --> WebApp: Session / token",
                "WebApp --> User: Logged in",
                "",
                "@enduml",
            ]
            return "\n".join(lines)
    
    elif diagram_type == "deployment":
        # Build deployment from infrastructure preferences
        infra = technical_prefs.get("infrastructure", ["Kubernetes", "Cloud"])
        
        lines = [
            "@startuml",
            "title Deployment Diagram (Simplified)",
            "",
            "node \"Cloud Region\" {",
            "  node \"Kubernetes Cluster\" {",
            "    node \"API Pod\" as api",
            "    node \"Web Pod\" as web",
            "  }",
            "  database db",
            "}",
            "",
            "@enduml",
        ]
        return "\n".join(lines)
    
    elif diagram_type == "logical":
        # Build logical view from actors or entities
        entities = []
        
        # Try to extract entity names from actors
        for actor in actors[:3]:
            if actor.get("type") == "person":
                entities.append(actor.get("name", "User"))
        
        # If no person actors, try to infer entities from primary flows
        if not entities and primary_flows:
            for flow in primary_flows[:2]:
                flow_name = flow.get("name", "")
                words = flow_name.split()
                for word in words:
                    if word not in ["The", "A", "An", "Display", "View", "Show"]:
                        entities.append(word)
                        break
        
        if not entities:
            entities = ["User", "Subscription"]
        
        lines = [
            "@startuml",
            "title Logical / Domain View",
            "",
        ]
        
        for entity in entities[:3]:  # Limit to 3
            entity_name = entity.replace(" ", "")
            lines.append(f'class {entity_name} {{')
            lines.append("  +id")
            if "User" in entity:
                lines.append("  +email")
            elif "Subscription" in entity or "Order" in entity:
                lines.append("  +status")
            elif "Video" in entity or "Metadata" in entity:
                lines.append("  +title")
                lines.append("  +description")
            else:
                lines.append("  +name")
            lines.append("}")
            lines.append("")
        
        # Add relationship if multiple entities
        if len(entities) >= 2:
            e1 = entities[0].replace(" ", "")
            e2 = entities[1].replace(" ", "")
            lines.append(f'{e1} "1" -- "*" {e2}')
        
        lines.extend(["", "@enduml"])
        return "\n".join(lines)
    
    else:
        # Fallback for unknown types
        lines = [
            "@startuml",
            "title Generic Diagram Stub",
            "",
            "note as N1",
            "  TODO: Replace this stub with a concrete diagram",
            "  for the requested type.",
            "end note",
            "",
            "@enduml",
        ]
        return "\n".join(lines)


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
