#!/usr/bin/env python3
"""
Generates docs/projects/index.md and _generated_projects_nav.yml from Workbench.

Env:
  WB_BASE  = https://workbench.shafie.org (default)
  WB_TOKEN = optional bearer or service token for Cloudflare/Access
"""
from __future__ import annotations
import json, os, sys, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROJ = DOCS / "projects"

PROJ.mkdir(parents=True, exist_ok=True)

base = os.getenv("WB_BASE", "https://workbench.shafie.org").rstrip("/")
url  = f"{base}/api/projects"

req = urllib.request.Request(url)
req.add_header("User-Agent", "ArchAiTectSync/1.0")
token = os.getenv("WB_TOKEN")
if token:
    # support either Bearer or a simple token; both are tried
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Workbench-Token", token)

def fetch():
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"::error::Fetching {url} failed: {e.code} {e.reason}")
    except Exception as e:
        print(f"::error::Fetching {url} failed: {e}")
    return None

items = fetch()
lines = ["# Projects", "", "<!-- GENERATED: do not edit by hand -->"]

if items and isinstance(items, list):
    # newest first if created_at exists
    def keyfn(x): return (x.get("created_at") or "", x.get("slug") or "")
    items = sorted(items, key=keyfn, reverse=True)
    for p in items:
        name = (p.get("name") or p.get("slug") or "").strip()
        slug = (p.get("slug") or "").strip()
        if slug and name:
            lines.append(f"- [{name}](../projects/{slug}/)")
else:
    # fallback: tell the reader why it’s empty
    lines += [
        "",
        "> _No projects available from Workbench right now._",
        "> This page is generated from the Workbench API. "
        "If you expect content here, check that Workbench `/api/projects` is reachable "
        "(Cloudflare Access or tokens may be required)."
    ]

(PROJ / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Global nav fragment
nav = ["- Projects:", "  - Overview: projects/index.md"]
if items:
    for p in items:
        name = (p.get("name") or p.get("slug") or "").replace(":", "\\:")
        slug = (p.get("slug") or "").strip()
        if slug and name:
            nav.append(f"  - {name}: projects/{slug}/index.md")

(DOCS / "_generated_projects_nav.yml").write_text("\n".join(nav) + "\n", encoding="utf-8")
(PROJ / "_nav.generated.yml").write_text("\n".join(nav) + "\n", encoding="utf-8")

print("Projects page sync complete.")
