# server/app.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.db import init_db
from server.routers import ui, brief, brief_ai, generate


BASE_DIR = Path(__file__).resolve().parent  # /home/n1mz/arch-workbench/server


def create_app() -> FastAPI:
    app = FastAPI(title="ArchAiTect Workbench")

    # --- DB init ------------------------------------------------------------
    init_db()

    # --- Templates (absolute path) -----------------------------------------
    app.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    # --- Static / assets (favicon, CSS, etc.) ------------------------------
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        # One StaticFiles instance, mounted on BOTH /static and /assets
        static_files = StaticFiles(directory=str(static_dir))
        app.mount("/static", static_files, name="static")
        app.mount("/assets", static_files, name="assets")

    # --- Routers -----------------------------------------------------------
    # HTML + JSON UI
    app.include_router(ui.router)

    # Brief + AI + generation JSON APIs under /api/projects/{slug}/...
    app.include_router(brief.router, prefix="/api/projects")
    app.include_router(brief_ai.router, prefix="/api/projects")
    app.include_router(generate.router, prefix="/api/projects")

    return app


app = create_app()
