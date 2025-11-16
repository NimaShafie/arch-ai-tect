from pathlib import Path
import json, subprocess
from .files import ensure_project_tree, write_yaml, write_json, render_project_index

PROMPTS_DIR = Path("prompts")  # put your 00/01/10/30/40/50 files here

def run_llm(prompt_path: Path, variables: dict) -> str:
    """
    Stub: call OpenWebUI/Ollama via your local endpoint OR shell tool.
    For now, return a placeholder string so the pipeline runs.
    """
    # e.g., requests.post(OPENWEBUI_URL, json={...})
    return f"// GENERATED from {prompt_path.name}\n// variables: {list(variables.keys())}\n"

def generate_all(slug: str, brief: dict, manifest: dict, refine: bool = True):
    base = ensure_project_tree(slug)
    # 1) Orchestrate core artifacts (use your 01_orchestrator.md contract)
    artifacts = {
        "package/spec.md": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "out": "spec"}),
        "package/reference-arch.md": run_llm(PROMPTS_DIR/"50_impl_guide.md", {"brief": brief, "manifest": manifest, "out": "ref-arch"}),
        "package/implementation-guide.md": run_llm(PROMPTS_DIR/"50_impl_guide.md", {"brief": brief, "manifest": manifest, "out": "impl"}),
        "package/srs.md": run_llm(PROMPTS_DIR/"40_srs_scaffold.md", {"brief": brief, "manifest": manifest}),
        "diagrams/c4-context.dsl": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "view":"c4-context"}),
        "diagrams/c4-container.dsl": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "view":"c4-container"}),
        "diagrams/component.dsl": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "view":"c4-component"}),
        "diagrams/deployment.puml": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "view":"deployment"}),
        "diagrams/sequence.puml": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "view":"sequence"}),
        "diagrams/logical.mmd": run_llm(PROMPTS_DIR/"01_orchestrator.md", {"brief": brief, "manifest": manifest, "view":"logical"}),
    }
    for rel, content in artifacts.items():
        (base/rel).write_text(content, encoding="utf-8")

    # 2) Optional refiners
    if refine:
        # run_llm(PROMPTS_DIR/"10_structurizr_refine.md", {...}) etc.
        pass

    # 3) write brief + manifest & index
    write_json(base/"brief.json", brief)
    write_yaml(base/"manifest.yaml", manifest)
    render_project_index(slug, manifest.get("name", slug), manifest.get("nav_title", manifest.get("name", slug)))

    return base
