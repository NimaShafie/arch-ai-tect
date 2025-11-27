# server/core/config.py

import os

# Shared secret used for Workbench session / signing
AW_SECRET = os.getenv("AW_SECRET", "dev-aw-secret-change-me")

# Name of the session cookie used by Workbench
SESSION_COOKIE = "aw_session"

# MkDocs base for preview links
DOCS_BASE = os.getenv("DOCS_BASE", "https://docs.shafie.org").rstrip("/")

# NEW — OpenWebUI API backend URL
OPENWEBUI_API_URL = os.getenv("OPENWEBUI_API_URL", "").rstrip("/")

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./workbench.db")

# LLM model (optional override)
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "qwen2.5")
