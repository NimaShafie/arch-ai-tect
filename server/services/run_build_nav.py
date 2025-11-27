# server/services/run_build_nav.py

from pathlib import Path
import re
import zlib

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
    size to match the 'Diagrams' heading (###) and insert a horizontal rule
    before them for extra separation.
    """
    def repl(match: re.Match) -> str:
        hashes = match.group(1)
        title = match.group(2).strip()
        if title in _SECTION_HEADINGS:
            # Add separator and normalize to ### <Title>
            return f"---\n\n### {title}"
        return match.group(0)

    pattern = re.compile(r"^(#+)\s+(.*)\s*$", re.MULTILINE)
    return pattern.sub(repl, text)


def _generate_requirements_from_plantuml(code: str, section_title: str | None) -> str:
    """
    Extract a rich, software-requirements-style description from the PlantUML
    text. The result is returned as a heading followed by a fenced
    ```markdown``` block so it renders in a 'markdown box' on the page.
    Inside the block we keep plain text (no markdown formatting).
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

    # If we still didn't extract anything, provide a generic but useful description
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

    heading = "#### Requirements derived from this diagram"
    if section_title:
        heading = f"#### Requirements for {section_title}"

    body = "\n".join(bullets)
    return f"{heading}\n\n```markdown\n{body}\n```"


def _inject_plantuml_link(body: str, section_title: str | None = None) -> str:
    """
    If the body contains a PlantUML code block, compute the encoded URL and
    prepend:
        - 'Open in PlantUML' link (HTML viewer)
        - the PNG image rendered by the PlantUML server
        - a collapsible <details> block wrapping the original source
        - a requirements-style markdown box under the source

    The original fenced block is left intact so Kroki / MkDocs plugins can
    still render as before.
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

    link_line = f"[Open in PlantUML]({viewer_url})"
    # Avoid duplicating on repeated runs
    if link_line in body:
        return body

    alt_label = section_title or "Diagram"
    alt_label = alt_label.strip()

    requirements_md = _generate_requirements_from_plantuml(code, section_title)

    wrapped_body = (
        f"{link_line}\n\n"
        f"![{alt_label}]({png_url})\n\n"
        "<details>\n"
        "<summary>Show PlantUML source</summary>\n\n"
        f"{body}\n\n"
        "</details>\n\n"
        f"{requirements_md}\n"
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
    throughout to clearly separate sections and diagrams.
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
            # Separator after each package section
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
            # rich requirements markdown box, while keeping original fenced
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


def main() -> None:
    print("Running build_nav() before starting mkdocs serve...")
    build_nav()
    print("Done.")

    print("Building combined project index pages...")
    build_project_indexes()
    print("Done building project index pages.")


if __name__ == "__main__":
    main()
