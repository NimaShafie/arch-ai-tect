# server/services/mkdocs_nav.py
from pathlib import Path
import yaml

DOCS_DIR = Path("docs")
PROJECTS_DIR = DOCS_DIR / "projects"
GENERATED_NAV = PROJECTS_DIR / "_nav.generated.yml"
PROJECTS_INDEX = PROJECTS_DIR / "index.md"

def _title_for(slug: str) -> str:
    manifest = PROJECTS_DIR / slug / "manifest.yaml"
    if manifest.exists():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            t = (data.get("nav_title") or data.get("name") or "").strip()
            if t:
                return t
        except Exception:
            pass
    return slug.replace("-", " ").title()

def build_nav():
    """
    Builds:
      - docs/projects/_nav.generated.yml  (not currently included in nav; kept for future)
      - docs/projects/index.md            (overview with correct relative links)
    """
    entries = []
    lines = ["# Projects", ""]

    if PROJECTS_DIR.exists():
        for child in sorted(PROJECTS_DIR.iterdir()):
            if not child.is_dir():
                continue
            slug = child.name
            if (child / "index.md").exists():
                title = _title_for(slug)
                # keep a generated nav list for possible later use
                entries.append({title: f"projects/{slug}/index.md"})
                # correct relative link from docs/projects/index.md to docs/projects/<slug>/index.md
                lines.append(f"- [{title}](./{slug}/index.md)")

    GENERATED_NAV.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_NAV.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")

    PROJECTS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
