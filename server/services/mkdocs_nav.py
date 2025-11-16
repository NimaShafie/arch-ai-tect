from pathlib import Path
import yaml

DOCS = Path("docs")
PROJECTS = DOCS / "projects"
GENERATED_NAV = DOCS / "_generated_projects_nav.yml"

def build_nav():
    entries = []
    if PROJECTS.exists():
        for p in sorted([d for d in PROJECTS.iterdir() if d.is_dir()]):
            idx = p / "index.md"
            if idx.exists():
                entries.append({ p.name: f"projects/{p.name}/index.md" })
    block = [{ "Projects": entries }] if entries else []
    GENERATED_NAV.write_text(yaml.safe_dump(block, sort_keys=False), encoding="utf-8")
