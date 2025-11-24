# server/app.py
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .routers.ui import router as ui_router
from .db import init_db

app = FastAPI(title="Architecture Workbench Registry")

# --- CORS so docs.shafie.org can fetch /api/projects, etc. ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------------------------------

# Static & favicon
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    ico = static_dir / "favicon.ico"
    if ico.exists():
        return FileResponse(str(ico))
    return HTMLResponse(status_code=204)

@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}

@app.api_route("/", methods=["GET", "POST", "HEAD"])
async def root(_: Request):
    return RedirectResponse(url="/ui", status_code=303)

templates = Jinja2Templates(directory="server/templates")
app.include_router(ui_router)
