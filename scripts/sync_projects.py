# scripts/sync_projects.py
import json, os, pathlib, urllib.request, urllib.error, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PROJECTS_DIR = DOCS / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

WORKBENCH_URL = os.getenv("WORKBENCH_URL", "https://workbench.shafie.org").rstrip("/")
API = f"{WORKBENCH_URL}/api/projects"

HEADERS = {}
cf_id = os.getenv("WB_CF_ID") or os.getenv("WORKBENCH_CF_ACCESS_CLIENT_ID")
cf_secret = os.getenv("WB_CF_SECRET") or os.getenv("WORKBENCH_CF_ACCESS_CLIENT_SECRET")
if cf_id and cf_secret:
    HEADERS["CF-Access-Client-Id"] = cf_id
    HEADERS["CF-Access-Client-Secret"] = cf_secret

req = urllib.request.Request(API, headers=HEADERS)
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        items = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"::error::Fetching {API} failed: {e.code} {e.reason}")
    sys.exit(1)
except Exception as e:
    print(f"::error::Fetching {API} failed: {e}")
    sys.exit(1)

# newest first if created_at present
def sort_key(x):
    return (x.get("created_at") or "", x.get("slug") or "")
items = sorted(items, key=sort_key, reverse=True)

# Write docs/projects/index.md
lines = ["# Projects", ""]
for p in items:
    name = (p.get("name") or p.get("slug") or "").strip()
    slug = p.get("slug") or ""
    if slug:
        lines.append(f"- [{name}](../projects/{slug}/)")
(PROJECTS_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Write global & local nav fragments
nav = ["- Projects:", "  - Overview: projects/index.md"]
for p in items:
    name = (p.get("name") or p.get("slug") or "").replace(":", "\\:")
    slug = p.get("slug") or ""
    if slug:
        nav.append(f"  - {name}: projects/{slug}/index.md")

(DOCS / "_generated_projects_nav.yml").write_text("\n".join(nav) + "\n", encoding="utf-8")
(PROJECTS_DIR / "_nav.generated.yml").write_text("\n".join(nav) + "\n", encoding="utf-8")

print("Projects page and nav fragments updated from Workbench.")
