from pathlib import Path
DOCS = Path("docs")
PROJECTS = DOCS / "projects"

def build_index():
    lines = ["# Projects", ""]
    if PROJECTS.exists():
        for d in sorted([p for p in PROJECTS.iterdir() if p.is_dir()]):
            if (d / "index.md").exists():
                slug = d.name
                title = slug.replace("-", " ").title()
                lines.append(f"- [{title}](/{PROJECTS.name}/{slug}/)")
    (PROJECTS / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    build_index()
