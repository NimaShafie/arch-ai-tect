# server/app.py
from pathlib import Path
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .routers.ui import router as ui_router
from .db import init_db

# ---- Settings from environment (with safe defaults) ----
# Comma-separated list of origins (e.g., "https://docs.shafie.org,https://nimashafie.github.io")
ALLOW_ORIGINS = [
    o.strip() for o in os.getenv("WORKBENCH_ALLOW_ORIGINS", "*").split(",")
    if o.strip()
]
ALLOW_ALL = ALLOW_ORIGINS == ["*"]

app = FastAPI(title="Architecture Workbench Registry")

# ---- CORS (so docs site can fetch /api/projects) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOW_ALL else ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS", "POST", "DELETE"],
    allow_headers=["*"],
)

# ---- Static & templates ----
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")

templates = Jinja2Templates(directory="server/templates")

@app.on_event("startup")
def _startup():
    init_db()

# Health
@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}

# Root -> UI
@app.api_route("/", methods=["GET", "POST", "HEAD"])
async def root(_: Request):
    return RedirectResponse(url="/ui", status_code=303)

# ---- Favicon handling (ico or svg fallback) ----
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    ico = static_dir / "favicon.ico"
    svg = static_dir / "favicon.svg"
    if ico.exists():
        return FileResponse(str(ico), media_type="image/x-icon")
    if svg.exists():
        # Let browsers accept SVG as favicon when .ico is not present
        return FileResponse(str(svg), media_type="image/svg+xml")
    return Response(status_code=204)

# (Optional) set no-cache headers for HTML pages served by this app (Workbench UI),
# so Cloudflare doesn’t cache those unexpectedly.
@app.middleware("http")
async def add_no_cache_for_html(request: Request, call_next):
    response = await call_next(request)
    ctype = response.headers.get("content-type", "")
    if ctype.startswith("text/html"):
        # Encourage edge + browser to revalidate
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Routers
app.include_router(ui_router)
