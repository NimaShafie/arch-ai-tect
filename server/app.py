# server/app.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.db import init_db
from server.routers import brief, brief_ai, ui, generate


def create_app() -> FastAPI:
    app = FastAPI(title="ArchAiTect Workbench")

    # Init DB
    init_db()

    # Templates
    app.templates = Jinja2Templates(directory="server/templates")

    # Static assets (optional)
    #
    # Only mount /assets if the directory actually exists to avoid
    # crashing the whole app when running on a fresh checkout or a
    # server that doesn't ship front-end assets.
    assets_dir = Path(__file__).parent / "assets"
    if assets_dir.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="assets",
        )

    # UI + API routers
    app.include_router(ui.router)        # Workbench HTML + JSON API
    app.include_router(brief.router)
    app.include_router(brief_ai.router)
    app.include_router(generate.router)

    # Root redirect to /ui
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/ui")

    return app


app = create_app()
