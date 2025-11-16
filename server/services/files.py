from pathlib import Path
import json, hashlib, yaml, time

ROOT = Path(".").resolve()
DOCS = ROOT / "docs" / "projects"

def ensure_project_tree(slug: str):
    base = DOCS / slug
    (base / "package").mkdir(parents=True, exist_ok=True)
    (base / "diagrams").mkdir(parents=True, exist_ok=True)
    return base

def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def write_yaml(path: Path, data: dict):
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def render_project_index(slug: str, name: str, nav_title: str):
    base = DOCS / slug
    md = f"""# {name}

This page aggregates all generated assets for **{name}**.

## Documents
- [Specification](package/spec.md)
- [System Requirements (SRS)](package/srs.md)
- [Reference Architecture](package/reference-arch.md)
- [Implementation Guide](package/implementation-guide.md)

## Diagrams
- C4 Context: `diagrams/c4-context.dsl`
- C4 Container: `diagrams/c4-container.dsl`
- Component: `diagrams/component.dsl`
- Deployment (PlantUML): `diagrams/deployment.puml`
- Sequence (PlantUML): `diagrams/sequence.puml`
- Logical (Mermaid): `diagrams/logical.mmd`

> Generated at {time.strftime("%Y-%m-%d %H:%M:%S")} (UTC).
"""
    (base / "index.md").write_text(md, encoding="utf-8")
