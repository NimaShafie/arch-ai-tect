# server/services/run_build_nav.py

from pathlib import Path
import re
import zlib
import html

from server.services.mkdocs_nav import build_nav


# Where all per-project docs live, relative to repo root
PROJECTS_ROOT = Path("docs") / "projects"

# PlantUML server base for direct links (HTML viewer + PNG image)
PLANTUML_SERVER_BASE = "https://uml.shafie.org"

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

    NOTE: We intentionally DO NOT add horizontal rules here anymore, so
    sections like Summary / Context / Actors / Key Scenarios read as a
    continuous block under Reference Architecture or Implementation Guide.
    """
    def repl(match: re.Match) -> str:
        hashes = match.group(1)
        title = match.group(2).strip()
        if title in _SECTION_HEADINGS:
            # Normalize to ### <Title> only (no extra --- separators)
            return f"### {title}"
        return match.group(0)

    pattern = re.compile(r"^(#+)\s+(.*)\s*$", re.MULTILINE)
    return pattern.sub(repl, text)


# --- PlantUML → requirements text --------------------------------------------

def _generate_requirements_from_plantuml(code: str, section_title: str | None) -> str:
    """
    Extract a rich, software-requirements-style description from the PlantUML
    text.

    Returns an HTML <details open> block with a summary title and an inner
    fenced ```markdown``` block so it still renders as markdown and can be
    copied/piped into downstream tools easily.
    """
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

        # C4 element definitions: Person/System/Container/Component(...)
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

        # Generic deployment / structural elements:
        # node "Cloud Region" as cloud, database "db" as db, component "WebApp" as web, etc.
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

    # If nothing parsed, provide a generic but useful description
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

    title = section_title or "Diagram"
    summary = f"Requirements for {title}"

    bullets_text = "\n".join(bullets)

    # details panel (blue box) + inner markdown fence
    return (
        f'<details open>\n'
        f'<summary>{html.escape(summary)}</summary>\n\n'
        f'```markdown\n{bullets_text}\n```\n\n'
        f'</details>'
    )


# --- PlantUML → Mermaid helpers (kept for future export, not rendered) -------

def _is_sequence_diagram(code: str) -> bool:
    if "sequence diagram" in code.lower():
        return True
    if re.search(r"^\s*actor\b", code, re.MULTILINE):
        return True
    if re.search(r"^\s*participant\b", code, re.MULTILINE):
        return True
    return False


def _plantuml_sequence_to_mermaid(code: str) -> str:
    lines = [ln.strip() for ln in code.splitlines()]
    actors: list[str] = []
    participants: list[str] = []
    messages: list[str] = []

    for ln in lines:
        if not ln or ln.startswith("'"):
            continue
        if ln.lower().startswith("@startuml") or ln.lower().startswith("@enduml"):
            continue
        if ln.startswith("!"):
            continue

        ma = re.match(r"actor\s+(\w+)", ln)
        if ma:
            name = ma.group(1)
            if name not in actors:
                actors.append(name)
            continue

        mp = re.match(r"participant\s+(\w+)", ln)
        if mp:
            name = mp.group(1)
            if name not in participants:
                participants.append(name)
            continue

        # message lines: A -> B : text   or A --> B : text
        mm = re.match(r"(\w+)\s*([-\.]+)>\s*(\w+)\s*:(.+)", ln)
        if mm:
            src, arrow_raw, dst, msg = (
                mm.group(1),
                mm.group(2),
                mm.group(3),
                mm.group(4).strip(),
            )
            # map arrows: request vs response (very rough)
            if "--" in arrow_raw:
                arrow = "-->>"
            else:
                arrow = "->>"
            messages.append(f"    {src}{arrow}{dst}: {msg}")
            continue

    if not actors and not participants and not messages:
        return ""

    out: list[str] = ["sequenceDiagram", ""]
    for a in actors:
        out.append(f"    actor {a}")
    for p in participants:
        out.append(f"    participant {p}")
    if actors or participants:
        out.append("")

    out.extend(messages)
    return "\n".join(out)


def _plantuml_c4_to_mermaid(code: str) -> str:
    """
    Very small translator from your C4-style PlantUML into a Mermaid flowchart.
    Intended for your current subset (Person/System/Container/Component + Rel).
    """
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

        # C4 elements
        m = re.match(
            r"(Person|System|Container|Component)\(([^,]+),\s*\"([^\"]+)\"(?:,\s*\"([^\"]+)\")?(?:,\s*\"([^\"]+)\")?",
            ln,
        )
        if m:
            kind, ident, name, tech_or_desc, desc2 = m.groups()
            # try to produce a multi-line label
            label_parts = [name]
            if tech_or_desc:
                label_parts.append(tech_or_desc)
            if desc2:
                label_parts.append(desc2)
            label = "\\n".join(label_parts)
            # make databases rounded, others rectangular
            if "db" in ident.lower() or "database" in name.lower():
                shape = f"{ident}[({label})]"
            else:
                shape = f"{ident}[{label}]"
            nodes[ident] = shape
            continue

        # Relationships
        r = re.match(r"Rel\(([^,]+),\s*([^,]+),\s*\"([^\"]+)\"", ln)
        if r:
            a, b, rel = (p.strip() for p in r.groups())
            edges.append((a, b, rel))
            continue

        # deployment-ish nodes: node "Cloud Region" as cloud, etc.
        d = re.match(
            r"(node|database|artifact|component|rectangle|queue|cloud|storage)\s+\"([^\"]+)\"\s+as\s+(\w+)",
            ln,
            re.IGNORECASE,
        )
        if d:
            kind, name, alias = d.groups()
            label = f"{name}"
            if kind.lower() in ("database", "storage"):
                shape = f"{alias}[({label})]"
            else:
                shape = f"{alias}[{label}]"
            nodes[alias] = shape
            continue

    if not nodes and not edges:
        return ""

    out: list[str] = ["flowchart LR", ""]
    for ident, shape in nodes.items():
        out.append(f"    {shape}")
    if nodes:
        out.append("")
    for a, b, rel in edges:
        out.append(f"    {a} -->|{rel}| {b}")

    return "\n".join(out)


def plantuml_to_mermaid(code: str) -> str:
    """
    Decide which translator to use (sequence vs C4/structural).
    Returns empty string if we cannot confidently translate.

    NOTE: This is currently NOT rendered into MkDocs pages; it's kept
    for export/automation purposes only.
    """
    if _is_sequence_diagram(code):
        return _plantuml_sequence_to_mermaid(code)
    # heuristic: if we see Rel( or Container( etc, treat as C4/structural
    if re.search(r"\b(Rel\(|Container\(|Person\(|System\()", code):
        return _plantuml_c4_to_mermaid(code)
    return ""


# --- Inject PlantUML into each diagram body -----------------------------------

def _inject_plantuml_link(body: str, section_title: str | None = None) -> str:
    """
    If the body contains a PlantUML code block, compute the encoded URL and
    prepend:
        - 'Open in PlantUML' link (HTML viewer, opens in new tab)
        - the PNG image rendered by the PlantUML server
        - a collapsible <details> block wrapping the original source
        - a requirements-style details+markdown block under the source

    We DO NOT render the Mermaid variant here to avoid showing two separate
    diagrams for the same section. Mermaid conversion is available via
    plantuml_to_mermaid(...) for export-only use.
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

    # HTML link so we can force target="_blank"
    link_line = (
        f'<a href="{html.escape(viewer_url)}" '
        f'target="_blank" rel="noopener">Open in PlantUML</a>'
    )
    # Avoid duplicating on repeated runs
    if link_line in body:
        return body

    alt_label = section_title or "Diagram"
    alt_label = alt_label.strip()

    requirements_block = _generate_requirements_from_plantuml(code, section_title)

    wrapped_body = (
        f"{link_line}\n\n"
        f"![{alt_label}]({png_url})\n\n"
        "<details>\n"
        "<summary>Show PlantUML source</summary>\n\n"
        f"{body}\n\n"
        "</details>\n\n"
        f"{requirements_block}\n"
    )

    return wrapped_body


# --- Project index generation --------------------------------------------------


def _read_without_leading_title(path: Path) -> str:
    """
    Read a markdown file and strip a single leading ATX heading line
    (e.g. '# Architecture Spec') so that we can inject our own
    '#### Architecture Spec' heading in the combined page.

    Also normalizes some internal headings and separators for better layout.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if lines and lines[0].lstrip().startswith("#"):
        # Drop the first line + any immediate empty lines
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    text = "\n".join(lines).strip()
    if not text:
        return ""

    # Normalize internal headings like Summary, Context, etc.
    text = _normalize_internal_headings(text)
    return text


def build_project_indexes() -> None:
    """
    For every docs/projects/<slug>/ directory, build a single index.md that
    inlines all package + diagram pages.

    Heading levels are slightly reduced so titles appear smaller:
      - Top title      -> ## (with explicit #top anchor)
      - Sections       -> ### (Package, Diagrams)
      - Subsections    -> #### (each spec/diagram)

    A 'Back to top' link is appended at the bottom. Horizontal rules are used
    between top-level package/diagram sections, but not inside Reference
    Architecture / Implementation Guide inner headings.
    """
    if not PROJECTS_ROOT.exists():
        print(f"[build_project_indexes] No {PROJECTS_ROOT} directory, skipping.")
        return

    for project_dir in sorted(PROJECTS_ROOT.iterdir()):
        if not project_dir.is_dir():
            continue

        slug = project_dir.name

        # Try to infer a nicer title from an existing title.txt, otherwise slug
        title = slug.replace("-", " ").title()
        title_file = project_dir / "title.txt"
        if title_file.exists():
            custom_title = title_file.read_text(encoding="utf-8").strip()
            if custom_title:
                title = custom_title

        print(f"[build_project_indexes] Building combined index for project '{slug}'")

        lines: list[str] = []

        # Explicit top-of-page anchor + slightly smaller main title
        lines.append('<a id="top"></a>')
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.append("This is the architecture workspace for this project.")
        lines.append("")

        # ----- Package section (smaller heading level) -----
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

            # Skip duplicate sections with identical bodies (avoids repeated
            # stub content like identical summaries across spec/SRS).
            body_key = body.strip()
            if body_key in seen_package_bodies:
                continue
            seen_package_bodies.add(body_key)

            lines.append(f"#### {section_title}")
            lines.append("")
            lines.append(body)
            lines.append("")
            # Separator after each top-level package section (spec, SRS, ref-arch, impl-guide)
            lines.append("---")
            lines.append("")

        # visual separation between package and diagrams
        lines.append("---")
        lines.append("")

        # ----- Diagrams section (smaller heading level) -----
        lines.append("### Diagrams")
        lines.append("")

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

            # Add PlantUML link + PNG image + collapsible source +
            # rich requirements details panel, while keeping original fenced
            # block intact.
            body = _inject_plantuml_link(body, section_title)
            lines.append(body)
            lines.append("")
            # EXTRA SEPARATOR between diagrams for visual clarity
            lines.append("---")
            lines.append("")

        # Back to top link at the very end
        lines.append("[Back to top](#top)")
        lines.append("")

        index_path = project_dir / "index.md"
        index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

        print(f"[build_project_indexes] Wrote {index_path}")

        # ----- Diagrams section (smaller heading level) -----
        lines.append("### Diagrams")
        lines.append("")

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

            # existing: inject PlantUML image + source + requirements panel
            body = _inject_plantuml_link(body, section_title)
            lines.append(body)
            lines.append("")
            lines.append("---")
            lines.append("")

        # --- Send to Pipeline button + Back to top link ---------------------

        # Button posts to the Workbench API for this project
        lines.append(
            f'<form action="https://workbench.shafie.org/api/projects/{slug}/pipeline" '
            f'method="post" style="margin-top:24px;margin-bottom:8px;">'
        )
        lines.append(
            '<button type="submit" '
            'style="padding:8px 16px; border-radius:4px; border:none; '
            'background:#1a73e8; color:#fff; cursor:pointer;">'
            'Send to Pipeline'
            '</button>'
        )
        lines.append("</form>")
        lines.append("")

        # Back to top anchor link (keep existing behavior)
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
