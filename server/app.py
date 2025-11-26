# server/app.py

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.db import init_db
from server.routers import brief, ui


def create_app() -> FastAPI:
    app = FastAPI(title="ArchAiTect Workbench")

    # Init DB
    init_db()

    # Templates
    app.templates = Jinja2Templates(directory="server/templates")

    # Static files (CSS, JS, etc.)
    app.mount("/static", StaticFiles(directory="server/static"), name="static")

    # Routers
    # ui router already defines /ui and /ui/{slug}
    app.include_router(ui.router)
    # brief API lives under /api/...
    app.include_router(brief.router, prefix="/api")

    # Root → UI landing
    @app.get("/", include_in_schema=False)
    async def root():
        # just bounce to /ui; ui_root will pick the first project
        return RedirectResponse(url="/ui", status_code=307)

    return app


app = create_app()
