# server/services/mkdocs_nav.py
from __future__ import annotations

from pathlib import Path
import yaml

DOCS_DIR = Path("docs")
PROJECTS_DIR = DOCS_DIR / "projects"
GENERATED_NAV = PROJECTS_DIR / "_nav.generated.yml"
PROJECTS_INDEX = PROJECTS_DIR / "index.md"


def _title_for(slug: str) -> str:
    """
    Determine a human-friendly title for a project slug, preferring manifest.yaml.
    """
    manifest = PROJECTS_DIR / slug / "manifest.yaml"
    if manifest.exists():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            t = (data.get("nav_title") or data.get("name") or "").strip()
            if t:
                return t
        except Exception:
            pass

    # Fallback: slug -> "My Project"
    raw = slug.replace("-", " ").strip()
    return raw.title() if raw else slug


def build_nav() -> None:
    """
    Scan docs/projects/* and regenerate:
      - docs/projects/_nav.generated.yml (for MkDocs nav inclusion)
      - docs/projects/index.md (simple project index page)
    """
    entries = []
    lines = ["# Projects", ""]

    if PROJECTS_DIR.exists():
        for child in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            slug = child.name
            index_md = child / "index.md"
            if not index_md.exists():
                continue

            title = _title_for(slug)

            # Entry for generated nav
            entries.append({title: f"projects/{slug}/index.md"})

            # Link line for projects/index.md (relative link)
            lines.append(f"- [{title}](./{slug}/index.md)")

    GENERATED_NAV.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_NAV.write_text(
        yaml.safe_dump(entries, sort_keys=False),
        encoding="utf-8",
    )

    PROJECTS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
