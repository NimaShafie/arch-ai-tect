
# server/services/orchestrator.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from .files import ensure_project_tree, write_json, write_yaml

DIAGRAM_META: Dict[str, Tuple[str, str, str]] = {
    "c4_context": ("plantuml/c4-context.puml", "plantuml", ".puml"),
    "c4_container": ("plantuml/c4-container.puml", "plantuml", ".puml"),
    "c4_component": ("plantuml/c4-component.puml", "plantuml", ".puml"),
    "sequence": ("plantuml/sequence-login.puml", "plantuml", ".puml"),
    "deployment": ("plantuml/c4-deployment.puml", "plantuml", ".puml"),
    "logical": ("mermaid/logical.mmd", "mermaid", ".mmd"),
}

TEMPLATES_ROOT = Path("templates/_arch")
DOCS_ROOT = Path("docs")

def _load_template(rel_path: str) -> str:
    path = TEMPLATES_ROOT / "diagrams" / rel_path
    return path.read_text(encoding="utf-8")

def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _index_md(project_name: str, slug: str) -> str:
    return f"""# {project_name}

This space is scaffolded and ready.

**Next steps (in the Workbench UI)**:
1. Fill the high-level brief → https://workbench.shafie.org/ui/{slug}#brief
2. Choose diagram types & dialects → https://workbench.shafie.org/ui/{slug}#choices
3. Generate artifacts → https://workbench.shafie.org/ui/{slug}#generate

Once generated, diagrams and specifications will appear here under this project.

## Diagrams

- [C4 Context](./diagrams/c4_context/)
- [C4 Container](./diagrams/c4_container/)
- [C4 Component](./diagrams/c4_component/)
- [Deployment](./diagrams/deployment/)
- [Sequence](./diagrams/sequence/)
- [Logical](./diagrams/logical/)
"""

def _package_md(template_name: str, project_name: str, brief: dict) -> str:
    try:
        raw = (TEMPLATES_ROOT / template_name).read_text(encoding="utf-8")
    except FileNotFoundError:
        raw = f"# {project_name}: {template_name.replace('.md','').replace('-',' ').title()}\n"
    return (
        raw.replace("{{PROJECT_NAME}}", project_name)
        .replace("{{BRIEF_JSON}}", "```json\n" + json.dumps(brief or {}, indent=2) + "\n```")
    )

def _diagram_md(project_name: str, name: str, lang: str, src: str) -> str:
    return f"""# {project_name} · {name.replace('_',' ').title()}

> Source is embedded below and rendered via Kroki/PlantUML.

```{lang}
{src.strip()}
```
"""

def _emit_diagram(project_dir: Path, project_name: str, key: str):
    meta = DIAGRAM_META.get(key)
    if not meta:
        return
    tpl_rel, lang, ext = meta
    src = _load_template(tpl_rel)
    src_dir = project_dir / "diagrams" / "src"
    _write(src_dir / f"{key}{ext}", src)
    page = _diagram_md(project_name, key, lang, src)
    _write(project_dir / "diagrams" / key / "index.md", page)

def generate_all(
    project_slug: str,
    project_name: str,
    brief_json: str,
    choices: List[str],
    refine: bool = False,
) -> None:
    ensure_project_tree(project_slug)
    project_dir = DOCS_ROOT / "projects" / project_slug
    project_dir.mkdir(parents=True, exist_ok=True)

    try:
        brief = json.loads(brief_json or "{}")
    except Exception:
        brief = {}

    _write(project_dir / "index.md", _index_md(project_name, project_slug))
    _write(project_dir / "package" / "spec.md", _package_md("spec.md", project_name, brief))
    _write(project_dir / "package" / "srs.md", _package_md("srs.md", project_name, brief))
    _write(project_dir / "package" / "reference-arch.md", _package_md("reference-arch.md", project_name, brief))
    _write(project_dir / "package" / "implementation-guide.md", _package_md("implementation-guide.md", project_name, brief))

    for key in choices or []:
        _emit_diagram(project_dir, project_name, key)

    manifest = {
        "name": project_name,
        "slug": project_slug,
        "choices": choices or [],
        "refine": bool(refine),
    }
    _write(project_dir / "manifest.yaml", write_yaml(manifest) or "")
    _write(project_dir / "brief.json", json.dumps(brief, indent=2))
