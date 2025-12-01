# server/app.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from server.db import init_db
from server.routers import (
    api,
    auth,
    brief,
    brief_ai,
    generate,
    ui,
    pipeline,
)


def create_app() -> FastAPI:
    """
    Main FastAPI application factory for ArchAiTect Workbench.
    """
    app = FastAPI(title="ArchAiTect Workbench")

    # Allow docs.shafie.org to call Workbench APIs (e.g. /api/projects) via fetch()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://docs.shafie.org"],
        allow_credentials=True,              # <-- changed from False
        allow_methods=["GET", "OPTIONS"],    # GET + preflight are enough
        allow_headers=["*"],
    )

    # Initialize DB (safe to call once at startup)
    init_db()

    # Templates
    templates_dir = Path(__file__).parent / "templates"
    app.templates = Jinja2Templates(directory=str(templates_dir))
    app.templates.env.auto_reload = True

    # Static files (CSS, JS, images)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # NEW: serve /assets/* from server/static so /assets/favicon.svg works
    app.mount("/assets", StaticFiles(directory="server/static"), name="assets")

    # Routers (keep existing behavior)
    app.include_router(api.router)
    app.include_router(auth.router)
    app.include_router(brief.router)
    app.include_router(brief_ai.router)
    app.include_router(generate.router)
    app.include_router(ui.router)
    app.include_router(pipeline.router)

    # Root redirect to UI
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/ui")

    return app


# Uvicorn entrypoint
app = create_app()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    # Serve the SVG as the favicon; most browsers are fine with this
    return FileResponse("server/static/favicon.svg", media_type="image/svg+xml")
