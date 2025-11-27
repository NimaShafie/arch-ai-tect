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


def _inject_plantuml_link(body: str, section_title: str | None = None) -> str:
    """
    If the body contains a PlantUML code block, compute the encoded URL and
    prepend:
        - 'Open in PlantUML' link (HTML viewer)
        - the PNG image rendered by the PlantUML server
        - a collapsible <details> block wrapping the original source

    The original fenced block is left intact so Kroki / MkDocs plugins can
    still render as before. We only wrap it in <details> so the source appears
    in a smaller, collapsible box.
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

    # Wrap the existing body (including the fenced code block) in <details>
    wrapped_body = (
        f"{link_line}\n\n"
        f"![{alt_label}]({png_url})\n\n"
        "<details>\n"
        "<summary>Show PlantUML source</summary>\n\n"
        f"{body}\n\n"
        "</details>"
    )

    return wrapped_body


# --- Project index generation --------------------------------------------------


def _read_without_leading_title(path: Path) -> str:
    """
    Read a markdown file and strip a single leading ATX heading line
    (e.g. '# Architecture Spec') so that we can inject our own
    '### Architecture Spec' heading in the combined page.

    If no heading is found on the first line, return the content as-is.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if lines and lines[0].lstrip().startswith("#"):
        # Drop the first line + any immediate empty lines
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    return "\n".join(lines).strip()


def build_project_indexes() -> None:
    """
    For every docs/projects/<slug>/ directory, build a single index.md that
    inlines all package + diagram pages.

    Heading levels are slightly reduced so titles appear smaller:
      - Top title      -> ## (with explicit #top anchor)
      - Sections       -> ### (Package, Diagrams)
      - Subsections    -> #### (each spec/diagram)

    A 'Back to top' link is appended at the bottom.
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
        for section_title, filename in PACKAGE_FILES:
            src = package_root / filename
            if not src.exists():
                continue

            lines.append(f"#### {section_title}")
            lines.append("")

            body = _read_without_leading_title(src)
            if body:
                lines.append(body)
                lines.append("")

        # visual separation between sections
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

            lines.append(f"#### {section_title}")
            lines.append("")

            body = _read_without_leading_title(src)
            if body:
                # Add PlantUML link + PNG image + collapsible source,
                # while keeping original fenced block intact.
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
