#!/usr/bin/env python3
"""
Generate docs/projects/index.md and the nav fragments from Workbench.
Never fails the build: on any fetch error, we write a minimal/fallback page.

Inputs (optional):
  WORKBENCH_URL  default: https://workbench.shafie.org
  OUTPUT_DIR     default: docs/projects
"""

import json
import os
import pathlib
import ssl
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT_DIR = DOCS / "projects"

BASE = os.getenv("WORKBENCH_URL", "https://workbench.shafie.org").rstrip("/")
API  = f"{BASE}/api/projects"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)

def fetch_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        },
        method="GET",
    )
    # tolerant SSL context
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            if resp.status != 200:
                raise urllib.error.HTTPError(url, resp.status, "bad status", resp.headers, None)
            data = resp.read()
            return json.loads(data.decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"::warning::Fetching {url} failed: {e}", file=sys.stderr)
        return None

def write_projects(items):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # sort newest first if created_at exists
    def key(p):
        return (p.get("created_at") or "", p.get("slug") or "")

    md_lines = ["# Projects", ""]
    nav = ["- Projects:", "  - Overview: projects/index.md"]

    if items:
        for p in sorted(items, key=key, reverse=True):
            name = (p.get("name") or p.get("slug") or "").strip()
            slug = (p.get("slug") or "").strip()
            if not slug:
                continue
            md_lines.append(f"- [{name}](../projects/{slug}/)")
            safe_name = name.replace(":", "\\:")
            nav.append(f"  - {safe_name}: projects/{slug}/index.md")
    else:
        md_lines += [
            "> _No projects found at the Workbench right now._",
            "",
            "This list is generated automatically during the docs build.",
        ]

    (OUT_DIR / "index.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (DOCS / "_generated_projects_nav.yml").write_text("\n".join(nav) + "\n", encoding="utf-8")
    (OUT_DIR / "_nav.generated.yml").write_text("\n".join(nav) + "\n", encoding="utf-8")

def main():
    items = fetch_json(API)
    if not isinstance(items, list):
        items = []
    write_projects(items)

if __name__ == "__main__":
    main()
