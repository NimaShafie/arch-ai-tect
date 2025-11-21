# server/core/config.py
import os

DOCS_BASE = os.getenv("DOCS_BASE", "https://docs.shafie.org")
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "https://ai.shafie.org")
OPENWEBUI_API_URL = os.getenv("OPENWEBUI_API_URL", "").strip()

AW_SECRET = os.getenv("AW_SECRET", "dev-secret-change-me")
SESSION_COOKIE = "aw_session"
SHOW_UNASSIGNED = os.getenv("AW_SHOW_UNASSIGNED", "0") == "1"
