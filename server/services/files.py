# server/services/files.py
from __future__ import annotations

from pathlib import Path
import json
import yaml
import subprocess
from typing import Any, Dict, Optional

# -----------------------------------------------------------------------------#
# Constants
# -----------------------------------------------------------------------------#

DOCS_DIR = Path("docs")
PROJECTS_DIR = DOCS_DIR / "projects"


# -----------------------------------------------------------------------------#
# Project tree helpers
# -----------------------------------------------------------------------------#

def ensure_project_tree(slug: str) -> Path:
    """
    Ensure the standard docs/projects/<slug> tree exists and return its path.

    Layout:
      docs/projects/<slug>/
        index.md
        brief.json
        manifest.yaml
        package/
          spec.md
          srs.md
          reference-arch.md
          implementation-guide.md
        diagrams/
          src/
          images/
    """
    base = PROJECTS_DIR / slug
    (base / "package").mkdir(parents=True, exist_ok=True)
    (base / "diagrams" / "src").mkdir(parents=True, exist_ok=True)
    (base / "diagrams" / "images").mkdir(parents=True, exist_ok=True)
    return base


# -----------------------------------------------------------------------------#
# Write helpers
# -----------------------------------------------------------------------------#

def write_json(path: Path, data: Any) -> str:
    """
    Write JSON to path and return the written text.
    Also triggers an optional MkDocs rebuild if inside docs/.
    """
    text = json.dumps(data, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _maybe_rebuild(path)
    return text


def write_yaml(path: Path, data: Any) -> str:
    """
    Write YAML to path and return the written text.
    Also triggers an optional MkDocs rebuild if inside docs/.
    """
    text = yaml.safe_dump(data, sort_keys=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _maybe_rebuild(path)
    return text


# -----------------------------------------------------------------------------#
# MkDocs rebuild hook (best-effort, non-fatal)
# -----------------------------------------------------------------------------#

def trigger_mkdocs_rebuild() -> None:
    """
    Optionally trigger a MkDocs rebuild or notify an external watcher that
    docs/ has changed. This is intentionally a best-effort, non-fatal call.

    You can implement:
      - a 'make docs' call
      - a 'touch' on some sentinel file
      - or leave as a no-op in local dev.
    """
    # By default, we do nothing to avoid surprises.
    # Uncomment or customize if you want automatic rebuilds.
    # try:
    #     subprocess.Popen(["make", "docs"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # except Exception:
    #     pass
    return


def _maybe_rebuild(path: Path) -> None:
    """
    Trigger a rebuild iff the written path is inside the docs/ tree.
    Never raises; failures are swallowed.
    """
    try:
        resolved = path.resolve()
        docs_root = DOCS_DIR.resolve()
        if docs_root in resolved.parents or resolved == docs_root:
            trigger_mkdocs_rebuild()
    except Exception:
        # Never crash the caller.
        pass
