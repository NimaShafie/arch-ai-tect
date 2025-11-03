#!/usr/bin/env python3
import os, sys, json, pathlib, re, base64
import requests
import yaml

# Config via env
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "").rstrip("/")
OPENWEBUI_APIKEY = os.getenv("OPENWEBUI_APIKEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "").rstrip("/")
MODEL = os.getenv("ARCHAI_MODEL", "qwen2.5:14b")  # pick what you run

PROMPT_PATH = "prompts/archaitect-json-spec.md"

def load_prompt():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def load_intake(intake_path):
    with open(intake_path, "r", encoding="utf-8") as f:
        data = f.read()
    # sanity: must not be untouched template
    if "TBD" in data:
        print("ERROR: intake.yaml still contains 'TBD' placeholders.")
        sys.exit(2)
    return data

def call_openwebui(prompt):
    # OpenWebUI compatible /v1/chat/completions
    url = f"{OPENWEBUI_URL}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENWEBUI_APIKEY}"} if OPENWEBUI_APIKEY else {}
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 6000
    }
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return content

def call_ollama(prompt):
    # Ollama /api/chat
    url = f"{OLLAMA_URL}/api/chat"
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "options": {"temperature": 0.2}}
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    # Ollama streams; collate messages
    data = r.json()
    content = ""
    if "message" in data and "content" in data["message"]:
        content = data["message"]["content"]
    elif "done" in data:
        # newer ollama might chunk; fall back if needed
        content = data.get("message", {}).get("content", "")
    return content

def write_file(base_dir, rel_path, content):
    p = pathlib.Path(base_dir, rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    if len(sys.argv) != 2:
        print("Usage: archaitect_generate.py packages/<package_id>/intake.yaml")
        sys.exit(1)
    intake_path = sys.argv[1]
    pkg_dir = str(pathlib.Path(intake_path).parent)
    package_id = pathlib.Path(pkg_dir).name

    prompt_tmpl = load_prompt()
    intake_yaml = load_intake(intake_path)
    prompt = prompt_tmpl.replace("{{INTAKE_YAML}}", intake_yaml)

    if OPENWEBUI_URL:
        raw = call_openwebui(prompt)
    elif OLLAMA_URL:
        raw = call_ollama(prompt)
    else:
        print("ERROR: Set either OPENWEBUI_URL or OLLAMA_URL in env.")
        sys.exit(3)

    # Strip code fences if any (just in case)
    raw = raw.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.DOTALL)

    try:
        obj = json.loads(raw)
    except Exception as e:
        print("ERROR: LLM did not return valid JSON:", e)
        print(raw[:1000])
        sys.exit(4)

    files = obj.get("files", {})
    if not files:
        print("ERROR: no 'files' object in JSON.")
        sys.exit(5)

    # simple writer
    for key, val in files.items():
        if key in ["diagrams"]:
            # nested shapes
            diags = val
            # PUML
            for name, content in diags.get("plantuml", {}).items():
                write_file(pkg_dir, f"diagrams/plantuml/{name}", content)
            # Mermaid
            for name, content in diags.get("mermaid", {}).items():
                write_file(pkg_dir, f"diagrams/mermaid/{name}", content)
        else:
            # top-level files
            # jira_issues.json and notion_tasks.json are stringified JSON in the spec; if string, keep as-is
            if isinstance(val, dict) or isinstance(val, list):
                write_file(pkg_dir, key, json.dumps(val, indent=2))
            else:
                write_file(pkg_dir, key, val)

    print(f"Generated files for package: {package_id}")

if __name__ == "__main__":
    main()
