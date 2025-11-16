#!/usr/bin/env python3
import argparse, json, yaml, subprocess
from pathlib import Path
from server.services.orchestrator import generate_all
from server.services.mkdocs_nav import build_nav

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--no-refine", action="store_true")
    args = ap.parse_args()
    base = Path(f"docs/projects/{args.slug}")
    brief = json.loads((base/"brief.json").read_text("utf-8"))
    manifest = yaml.safe_load((base/"manifest.yaml").read_text("utf-8"))
    generate_all(args.slug, brief, manifest, refine=not args.no_refine)
    build_nav()
    print(f"Docs: docs/projects/{args.slug}/index.md")
if __name__ == "__main__":
    main()
