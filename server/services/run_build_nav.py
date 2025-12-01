# server/services/run_build_nav.py

from pathlib import Path
import re
import zlib
import html
import os
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from server.services.mkdocs_nav import build_nav

# Where all per-project docs live, relative to repo root
PROJECTS_ROOT = Path("docs") / "projects"

# PlantUML server base for public links (HTML viewer + PNG image)
PLANTUML_SERVER_BASE = "https://uml.shafie.org"

# Optional override for the *pipeline* PNG fetches (internal PlantUML)
PIPELINE_PLANTUML_BASE = os.getenv("PIPELINE_PLANTUML_BASE", PLANTUML_SERVER_BASE)

# Files we expect under each project, grouped by section
# NOTE: these names are aligned with docs/projects/*/package
PACKAGE_FILES = [
    ("Architecture Spec", "spec.md"),
    ("Software Requirements Spec (SRS)", "srs.md"),
    ("Reference Architecture", "reference-arch.md"),
    ("Implementation Guide", "implementation-guide.md"),
]

# NOTE: these names are aligned with docs/projects/*/diagrams
DIAGRAM_FILES = [
    ("C4 Context", "c4_context.md"),
    ("C4 Container", "c4_container.md"),
    ("C4 Component", "c4_component.md"),
    ("Logical View", "logical.md"),
    ("Deployment View", "deployment.md"),
    ("Sequence Diagram", "sequence.md"),
]

# --- PlantUML encoding helpers ------------------------------------------------

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _deflate(data: bytes) -> bytes:
    """
    Raw DEFLATE (no zlib header) as expected by the PlantUML server.
    """
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(data) + compressor.flush()
    return compressed


def _encode_6bit(b: int) -> str:
    return _ALPHABET[b & 0x3F]


def _encode_3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return "".join(_encode_6bit(c) for c in (c1, c2, c3, c4))


def encode_plantuml(text: str) -> str:
    """
    Encode PlantUML text into the compact URL-safe format used by the PlantUML
    server, following the official deflate + 6-bit encoding.
    """
    data = text.encode("utf-8")
    compressed = _deflate(data)

    res: list[str] = []
    i = 0
    length = len(compressed)
    while i < length:
        b1 = compressed[i]
        b2 = compressed[i + 1] if i + 1 < length else 0
        b3 = compressed[i + 2] if i + 2 < length else 0
        res.append(_encode_3bytes(b1, b2, b3))
        i += 3
    return "".join(res)


_PLANTUML_BLOCK_RE = re.compile(
    r"```(?:kroki-)?plantuml\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)

# --- Heading / body utilities -------------------------------------------------

_SECTION_HEADINGS = {
    "Summary",
    "Context",
    "Actors",
    "Key Scenarios",
    "Overview",
    "Next Steps",
}


def _normalize_internal_headings(text: str) -> str:
    """
    For internal headings like 'Summary', 'Context', etc., standardize their
    size to match the 'Diagrams' heading (###).

    We deliberately DO NOT add horizontal rules here, so you don’t get
    duplicate separators at the bottom of the page.
    """

    def repl(match: re.Match) -> str:
        hashes = match.group(1)
        title = match.group(2).strip()
        if title in _SECTION_HEADINGS:
            return f"### {title}"
        return match.group(0)

    pattern = re.compile(r"^(#+)\s+(.*)\s*$", re.MULTILINE)
    return pattern.sub(repl, text)


# --- PlantUML → requirements text --------------------------------------------


def _requirements_bullets_from_plantuml(
    code: str, section_title: str | None
) -> list[str]:
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
                f"the message '{msg}' to {dst}, and the platform must be able "
                f"to process this exchange end-to-end."
            )
            continue

        # C4 relationship: Rel(a, b, "Uses")
        m = re.match(r"Rel\(([^,]+),\s*([^,]+),\s*\"([^\"]+)\"", ln)
        if m:
            a, b, rel = (p.strip() for p in m.groups())
            bullets.append(
                f"- The architecture shall include a relationship where "
                f"{a} {rel.lower()} {b}, and this connection must be "
                f"implemented with appropriate protocols, security, and error handling."
            )
            continue

        # C4 element definitions
        m = re.match(
            r"(Person|System|Container|Component)\(([^,]+),\s*\"([^\"]+)\"(?:,\s*\"([^\"]+)\")?",
            ln,
        )
        if m:
            kind, ident, name, desc = m.groups()
            desc_part = f" ({desc})" if desc else ""
            bullets.append(
                f"- The design shall define a {kind.lower()} {ident} named "
                f"{name}{desc_part}, and implementation work must provision it "
                f"as a distinct deployable or conceptual element."
            )
            continue

        # Generic deployment / structural elements
        m = re.match(
            r"(node|database|artifact|component|rectangle|queue|cloud|storage)\s+\"([^\"]+)\"\s+as\s+(\w+)",
            ln,
            re.IGNORECASE,
        )
        if m:
            kind, name, alias = m.groups()
            bullets.append(
                f"- The deployment model shall include a {kind.lower()} "
                f"{alias} representing {name}, and infrastructure tasks must "
                f"ensure it is provisioned, monitored, and reachable by its peers."
            )
            continue

        # Simple 'database db' style (no quoted name)
        m = re.match(r"database\s+(\w+)", ln, re.IGNORECASE)
        if m:
            alias = m.group(1)
            bullets.append(
                f"- The deployment model shall include a database {alias}, and "
                f"infrastructure tasks must provision, secure, and monitor it."
            )
            continue

    if not bullets:
        title = section_title or "this diagram"
        bullets.append(
            f"- This diagram defines the primary elements and relationships for {title}, "
            f"and implementation must ensure that all shown components, connections, and "
            f"responsibilities are realized in code, configuration, and infrastructure."
        )

    bullets.append(
        "- The development team shall treat each visual element as either a deployable "
        "artifact, a runtime capability, or an integration point, and create tasks to "
        "build, configure, and test each of them."
    )
    bullets.append(
        "- Non-functional requirements (performance, security, observability, "
        "resilience) must be applied to all links and components shown in the diagram."
    )

    return bullets


def _generate_requirements_from_plantuml(
    code: str, section_title: str | None
) -> str:
    bullets = _requirements_bullets_from_plantuml(code, section_title)
    bullets_text = "\n".join(bullets)

    title = section_title or "Diagram"
    summary = f"Requirements for {title}"

    return (
        f"<details open>\n"
        f"<summary>{html.escape(summary)}</summary>\n\n"
        f"```markdown\n{bullets_text}\n```\n\n"
        f"</details>"
    )


# --- PlantUML → PNG helper for pipeline --------------------------------------


def save_pipeline_png_from_body(body: str, dest: Path) -> None:
    """
    For pipeline exports only:

    - Find the first PlantUML block in the markdown body
    - Encode it
    - Download the PNG from the PlantUML server
    - Save it to 'dest'

    Any network / HTTP errors are logged to stdout and silently ignored so that
    the pipeline still succeeds and at least the markdown/requirements update.
    """
    match = _PLANTUML_BLOCK_RE.search(body)
    if not match:
        return

    code = match.group(1).strip()
    if not code:
        return

    encoded = encode_plantuml(code)

    # Use the pipeline-specific base (internal PlantUML) so we don't hit
    # Cloudflare challenges from the backend service.
    png_url = f"{PIPELINE_PLANTUML_BASE}/png/{encoded}"

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(png_url, timeout=20) as resp:
            data = resp.read()
        dest.write_bytes(data)
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        # Soft-fail: don't break the pipeline on image download problems
        print(f"[pipeline] WARNING: failed to fetch PNG from {png_url}: {exc}")


# --- PlantUML → Mermaid helpers (for Workbench diagrams view) ----------------
# (unchanged…)
#  [all the plantuml_to_mermaid helpers and _inject_plantuml_link stay exactly
#   as in your current file; omitted here only for brevity in this comment,
#   but keep them as-is from your version above.]
#   ↓↓↓

def _is_sequence_diagram(code: str) -> bool:
    if "sequence diagram" in code.lower():
        return True
    if re.search(r"^\s*actor\b", code, re.MULTILINE):
        return True
    if re.search(r"^\s*participant\b", code, re.MULTILINE):
        return True
    return False


def _plantuml_sequence_to_mermaid(code: str) -> str:
    lines = [ln.rstrip() for ln in code.splitlines()]
    actors: list[str] = []
    participants: list[str] = []
    messages: list[str] = []
    notes: list[str] = []

    for ln in lines:
        stripped = ln.strip()
        if not stripped or stripped.startswith("'"):
            continue
        low = stripped.lower()
        if low.startswith("@startuml") or low.startswith("@enduml"):
            continue
        if stripped.startswith("!"):
            continue

        ma = re.match(r"actor\s+(\w+)", stripped)
        if ma:
            name = ma.group(1)
            if name not in actors:
                actors.append(name)
            continue

        mp = re.match(r"participant\s+(\w+)", stripped)
        if mp:
            name = mp.group(1)
            if name not in participants:
                participants.append(name)
            continue

        mm = re.match(r"(\w+)\s*([-\.]+)>\s*(\w+)\s*:(.+)", stripped)
        if mm:
            src, arrow_raw, dst, msg = (
                mm.group(1),
                mm.group(2),
                mm.group(3),
                mm.group(4).strip(),
            )
            if "--" in arrow_raw or ".." in arrow_raw:
                arrow = "-->>"
            else:
                arrow = "->>"
            messages.append(f"    {src}{arrow}{dst}: {msg}")
            continue

        note = re.match(
            r"note\s+over\s+([A-Za-z0-9_, ]+)\s*:\s*(.+)", stripped, re.IGNORECASE
        )
        if note:
            who, text = note.groups()
            notes.append(f"    Note over {who.strip()}: {text.strip()}")
            continue

    if not actors and not participants and not messages and not notes:
        return ""

    out: list[str] = ["sequenceDiagram", ""]
    for a in actors:
        out.append(f"    actor {a}")
    for p in participants:
        out.append(f"    participant {p}")
    if actors or participants:
        out.append("")

    out.extend(messages)
    if notes:
        out.append("")
        out.extend(notes)

    return "\n".join(out)


def _plantuml_class_to_mermaid(code: str) -> str:
    """
    Handle simple UML class diagrams like the Logical View stub.

    We preserve class attributes and simple associations such as:
      User "1" -- "*" Subscription
    """
    classes: dict[str, list[str]] = {}
    relations: list[str] = []

    current_class: str | None = None

    for raw in code.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("'"):
            continue
        if ln.lower().startswith("@startuml") or ln.lower().startswith("@enduml"):
            continue
        if ln.startswith("!"):
            continue

        # class User {  /  class Subscription {
        m = re.match(r"class\s+(\w+)\s*\{?", ln)
        if m:
            current_class = m.group(1)
            classes.setdefault(current_class, [])
            # If line ends with '{', attributes follow on subsequent lines.
            if ln.endswith("{"):
                continue
            else:
                current_class = None
            continue

        if ln == "}" and current_class:
            current_class = None
            continue

        # Inside a class body: treat as attribute
        if current_class:
            if ln:
                classes.setdefault(current_class, []).append(ln)
            continue

        # Association with cardinalities: User "1" -- "*" Subscription
        m = re.match(r"(\w+)\s+\"([^\"]*)\"\s+--\s+\"([^\"]*)\"\s+(\w+)", ln)
        if m:
            src, left_card, right_card, dst = m.groups()
            relations.append(
                f'    {src} "{left_card}" -- "{right_card}" {dst}'
            )
            continue

    if not classes and not relations:
        return ""

    out: list[str] = ["classDiagram", ""]

    # Classes + attributes
    for name, attrs in classes.items():
        if attrs:
            out.append(f"    class {name} {{")
            for attr in attrs:
                out.append(f"        {attr}")
            out.append("    }")
        else:
            out.append(f"    class {name}")
    if classes:
        out.append("")

    # Relations
    out.extend(relations)

    return "\n".join(out)


def _plantuml_c4_to_mermaid(code: str) -> str:
    lines = [ln.strip() for ln in code.splitlines()]
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []

    for ln in lines:
        if not ln or ln.startswith("'"):
            continue
        if ln.lower().startswith("@startuml") or ln.lower().startswith("@enduml"):
            continue
        if ln.startswith("!"):
            continue

        m = re.match(
            r"(Person|System|Container|Component)\(([^,]+),\s*\"([^\"]+)\"(?:,\s*\"([^\"]+)\")?(?:,\s*\"([^\"]+)\")?",
            ln,
        )
        if m:
            kind, ident, name, tech_or_desc, desc2 = m.groups()
            label_parts = [name]
            if tech_or_desc:
                label_parts.append(tech_or_desc)
            if desc2:
                label_parts.append(desc2)
            label = "<br/>".join(label_parts)
            if "db" in ident.lower() or "database" in name.lower():
                shape = f"{ident}[({label})]"
            else:
                shape = f"{ident}[{label}]"
            nodes[ident] = shape
            continue

        r = re.match(r"Rel\(([^,]+),\s*([^,]+),\s*\"([^\"]+)\"", ln)
        if r:
            a, b, rel = (p.strip() for p in r.groups())
            edges.append((a, b, rel))
            continue

        # node "Something" as alias
        d = re.match(
            r"(node|database|artifact|component|rectangle|queue|cloud|storage)\s+\"([^\"]+)\"\s+as\s+(\w+)",
            ln,
            re.IGNORECASE,
        )
        if d:
            kind, name, alias = d.groups()
            label = name
            if kind.lower() in ("database", "storage"):
                shape = f"{alias}[({label})]"
            else:
                shape = f"{alias}[{label}]"
            nodes[alias] = shape
            continue

        # Bare node "Cloud Region" { ... }  – treat as simple node
        d2 = re.match(r"node\s+\"([^\"]+)\"", ln, re.IGNORECASE)
        if d2:
            name = d2.group(1)
            alias = re.sub(r"\W+", "_", name).lower()
            if alias not in nodes:
                nodes[alias] = f"{alias}[{name}]"
            continue

        # Simple 'database db' form (no quoted name)
        db_simple = re.match(r"database\s+(\w+)", ln, re.IGNORECASE)
        if db_simple:
            alias = db_simple.group(1)
            if alias not in nodes:
                nodes[alias] = f"{alias}[({alias})]"
            continue

        msg_rel = re.match(r"(\w+)\s*[-\.]+>\s*(\w+)\s*:(.+)", ln)
        if msg_rel:
            a, b, rel = msg_rel.group(1), msg_rel.group(2), msg_rel.group(3).strip()
            edges.append((a, b, rel))
            continue

    if not nodes and not edges:
        return ""

    out: list[str] = ["flowchart LR", ""]
    for ident, shape in nodes.items():
        out.append(f"    {shape}")
    if nodes:
        out.append("")
    for a, b, rel in edges:
        if rel:
            out.append(f"    {a} -->|{rel}| {b}")
        else:
            out.append(f"    {a} --> {b}")

    return "\n".join(out)


def plantuml_to_mermaid(code: str) -> str:
    """
    Dispatch PlantUML → Mermaid:
      - sequenceDiagram for sequence diagrams
      - classDiagram for simple UML class diagrams (Logical View)
      - flowchart LR for C4/deployment-ish diagrams
    """
    if _is_sequence_diagram(code):
        return _plantuml_sequence_to_mermaid(code)

    # Logical / class diagrams
    if re.search(r"^\s*class\s+\w+", code, re.MULTILINE):
        mer = _plantuml_class_to_mermaid(code)
        if mer:
            return mer

    # C4 / deployment style
    if re.search(r"\b(Rel\(|Container\(|Person\(|System\()", code) or "node " in code:
        return _plantuml_c4_to_mermaid(code)

    return ""


# --- Inject PlantUML into each diagram body (MkDocs only) --------------------


def _inject_plantuml_link(body: str, section_title: str | None = None) -> str:
    """
    For each diagram markdown body (used on the MkDocs Projects pages):

      - Detect the first ```plantuml``` or ```kroki-plantuml``` block
      - Generate a PlantUML "Open in PlantUML" link
      - Render a PNG from the PlantUML server
      - Show a collapsible panel with JUST the PlantUML source
      - Append the auto-generated requirements block

    We do NOT wrap the entire original body anymore inside <details>,
    because that can confuse MkDocs/Kroki processing and makes the UI noisy.
    """
    match = _PLANTUML_BLOCK_RE.search(body)
    if not match:
        return body

    code = match.group(1).strip()
    if not code:
        return body

    encoded = encode_plantuml(code)
    viewer_url = f"{PLANTUML_SERVER_BASE}/uml/{encoded}"
    png_url = f"{PLANTUML_SERVER_BASE}/png/{encoded}"

    link_line = (
        f'<a href="{html.escape(viewer_url)}" '
        f'target="_blank" rel="noopener">Open in PlantUML</a>'
    )

    alt_label = (section_title or "Diagram").strip()
    requirements_block = _generate_requirements_from_plantuml(code, section_title)

    wrapped_body = (
        f"{link_line}\n\n"
        f"![{alt_label}]({png_url})\n\n"
        "<details>\n"
        "<summary>Show PlantUML source</summary>\n\n"
        f"```plantuml\n{code}\n```\n\n"
        "</details>\n\n"
        f"{requirements_block}\n"
    )

    return wrapped_body


# --- Pipeline exporter helpers -----------------------------------------------


def build_pipeline_diagram_markdown(
    body: str,
    section_title: str,
    project_slug: str,
    image_rel_path: Path | None = None,
) -> str:
    """
    Build the GitHub-friendly diagram page:

      # Title
      [Open in PlantUML](...)
      ![Diag](images/...)  (if image_rel_path provided)
      ## Requirements
      ...
      ```plantuml
      @startuml
      ...
      @enduml
      ```
      ---
      _Source: generated from ArchAiTect Workbench(...)

    If image_rel_path is None, we fall back to PlantUML PNG URLs so that the
    page is still usable even if offline PNG generation failed for some reason.
    """
    match = _PLANTUML_BLOCK_RE.search(body)
    if match:
        code = match.group(1).strip()
    else:
        code = ""

    encoded = encode_plantuml(code) if code else ""
    viewer_url = (
        f"{PLANTUML_SERVER_BASE}/uml/{encoded}" if encoded else ""
    )
    png_url = (
        f"{PLANTUML_SERVER_BASE}/png/{encoded}" if encoded else ""
    )

    bullets = _requirements_bullets_from_plantuml(code or "", section_title)
    source_url = f"https://workbench.shafie.org/projects/{project_slug}/"

    out: list[str] = []
    out.append(f"# {section_title}")
    out.append("")

    if viewer_url:
        out.append(f"[Open in PlantUML]({viewer_url})")
        out.append("")
    else:
        out.append("_No PlantUML source detected for this diagram._")
        out.append("")

    alt_label = f"{section_title} diagram"

    if image_rel_path is not None:
        # Preferred: local PNG inside the Disney repo
        out.append(f"![{alt_label}]({image_rel_path.as_posix()})")
        out.append("")
    elif png_url:
        # Fallback: render directly from PlantUML server
        out.append(f"![{alt_label}]({png_url})")
        out.append("")

    out.append("## Requirements")
    out.append("")
    out.extend(bullets)
    out.append("")

    # NEW: embed PlantUML source directly under Requirements (before the ---)
    if code:
        out.append("```plantuml")
        out.append(code)
        out.append("```")
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        f"_Source: generated from "
        f"[ArchAiTect Workbench]({source_url})_"
    )
    out.append("")
    return "\n".join(out)


# --- Project index generation -------------------------------------------------
# (everything below here stays exactly the same as your current file)
#  [build_project_indexes(), main(), etc.]

def _read_without_leading_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    text = "\n".join(lines).strip()
    if not text:
        return ""

    text = _normalize_internal_headings(text)
    return text


def build_project_indexes() -> None:
    if not PROJECTS_ROOT.exists():
        print(f"[build_project_indexes] No {PROJECTS_ROOT} directory, skipping.")
        return

    for project_dir in sorted(PROJECTS_ROOT.iterdir()):
        if not project_dir.is_dir():
            continue

        slug = project_dir.name

        title = slug.replace("-", " ").title()
        title_file = project_dir / "title.txt"
        if title_file.exists():
            custom_title = title_file.read_text(encoding="utf-8").strip()
            if custom_title:
                title = custom_title

        print(f"[build_project_indexes] Building combined index for project '{slug}'")

        lines: list[str] = []

        lines.append("---")
        lines.append(f"title: {title}")
        lines.append("---")
        lines.append("")

        lines.append('<a id="top"></a>')
        lines.append("")
        lines.append("This is the architecture workspace for this project.")
        lines.append("")

        # Package
        lines.append("### Package")
        lines.append("")

        package_root = project_dir / "package"
        seen_package_bodies: set[str] = set()

        for section_title, filename in PACKAGE_FILES:
            src = package_root / filename
            if not src.exists():
                continue

            body = _read_without_leading_title(src)
            if not body:
                continue

            body_key = body.strip()
            if body_key in seen_package_bodies:
                continue
            seen_package_bodies.add(body_key)

            lines.append(f"#### {section_title}")
            lines.append("")
            lines.append(body)
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("### Diagrams")
        lines.append("")

        # Diagrams
        diagrams_root = project_dir / "diagrams"
        for section_title, filename in DIAGRAM_FILES:
            src = diagrams_root / filename
            if not src.exists():
                continue

            body = _read_without_leading_title(src)
            if not body:
                continue

            lines.append(f"#### {section_title}")
            lines.append("")

            body = _inject_plantuml_link(body, section_title)
            lines.append(body)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Send to Pipeline button and helpers (unchanged)
        lines.append(
            f'<button type="button" '
            f'onclick="awSendToPipeline(\'{slug}\')" '
            'style="padding:8px 16px; border-radius:4px; border:none; '
            'background:#1a73e8; color:#fff; cursor:pointer; margin-top:24px;">'
            "Send to Pipeline"
            "</button>"
        )
        lines.append("")

        lines.append(
            f'<div id="aw-pipeline-modal-{slug}" '
            'style="display:none; position:fixed; inset:0; '
            'background:rgba(0,0,0,0.35); z-index:9999;">'
            '<div style="max-width:520px; margin:10% auto; background:#fff; '
            'border-radius:8px; padding:16px 20px; box-shadow:0 4px 16px rgba(0,0,0,0.25);">'
            '<div style="font-weight:700; margin-bottom:8px;">Pipeline Status</div>'
            f'<div id="aw-pipeline-status-{slug}" '
            'class="md-typeset" '
            'style="font-size:0.9rem; line-height:1.4;"></div>'
            '<div style="margin-top:16px; text-align:right;">'
            f'<button type="button" onclick="awClosePipeline(\'{slug}\')" '
            'style="padding:6px 12px; border-radius:4px; border:none; '
            'background:#e0e0e0; cursor:pointer;">Close</button>'
            "</div></div></div>"
        )
        lines.append("")

        lines.append(
            f'<iframe id="aw-pipeline-frame-{slug}" '
            f'name="aw-pipeline-frame-{slug}" '
            'style="display:none; width:0; height:0; border:none;"></iframe>'
        )
        lines.append("")

        lines.append(
            f'<form id="aw-pipeline-form-{slug}" '
            f'action="https://workbench.shafie.org/api/projects/{slug}/pipeline" '
            f'method="get" target="aw-pipeline-frame-{slug}" '
            'style="display:none;">'
            '<input type="hidden" name="source" value="docs.shafie.org" />'
            "</form>"
        )
        lines.append("")

        js = f"""
<script>
function awSendToPipeline(slug) {{
  const modal    = document.getElementById('aw-pipeline-modal-' + slug);
  const statusEl = document.getElementById('aw-pipeline-status-' + slug);
  const frame    = document.getElementById('aw-pipeline-frame-' + slug);
  const form     = document.getElementById('aw-pipeline-form-' + slug);
  if (!modal || !statusEl || !frame || !form) return;

  const runAt = new Date();

  modal.style.display = 'block';
  statusEl.textContent =
    'Triggering the pipeline export for this project…';

  const ghBase     = 'https://github.com/SevDev21/disney-ai-plus/tree/master';
  const ghArch     = ghBase + '/docs/architecture';
  const ghDiagrams = ghBase + '/docs/diagrams/' + slug;

  frame.onload = function () {{
    const ts = runAt.toLocaleString();
    statusEl.innerHTML =
      '<p>The pipeline export request was sent successfully.</p>' +
      '<p>If there were changes, you should see a new commit in GitHub within a few seconds.</p>' +
      '<p><strong>Last export run at:</strong> ' + ts + '</p>' +
      '<p>Quick links:</p>' +
      '<ul>' +
      '<li><a href="' + ghArch + '" target="_blank" rel="noopener">Architecture docs folder</a></li>' +
      '<li><a href="' + ghDiagrams + '" target="_blank" rel="noopener">Diagrams for this project</a></li>' +
      '</ul>';
  }};
  frame.onerror = function () {{
    const ts = runAt.toLocaleString();
    const pipelineUrl = form.action + '?source=docs.shafie.org';
    statusEl.innerHTML =
      '<p style="color:#b00020; font-weight:600;">' +
      'The pipeline request failed or returned an unexpected response.' +
      '</p>' +
      '<p>You can retry from this page, or open the pipeline endpoint directly:</p>' +
      '<p><a href="' + pipelineUrl + '" target="_blank" rel="noopener">' +
      pipelineUrl + '</a></p>' +
      '<p><strong>Last attempted run at:</strong> ' + ts + '</p>';
  }};

  form.submit();
}}
function awClosePipeline(slug) {{
  const modal = document.getElementById('aw-pipeline-modal-' + slug);
  if (modal) modal.style.display = 'none';
}}
</script>
""".strip()

        lines.append(js)
        lines.append("")

        lines.append("[Back to top](#top)")
        lines.append("")

        index_path = project_dir / "index.md"
        index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

        print(f"[build_project_indexes] Wrote {index_path}")


def main() -> None:
    print("Running build_nav() before starting mkdocs serve...")
    build_nav()
    print("Done.")

    print("Building combined project index pages...")
    build_project_indexes()
    print("Done building project index pages.")


if __name__ == "__main__":
    main()
