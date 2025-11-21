# server/routers/auth.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt

from ..db import get_session
from ..models import User
from ..core.session import set_user, clear

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")

def ctx(request: Request, **extra):
    base = {"request": request}
    base.update(extra); return base

@router.get("/auth", response_class=HTMLResponse, include_in_schema=False)
def auth_tabs(request: Request):
    return templates.TemplateResponse("auth.html", ctx(request, title="Account"))

@router.post("/auth/register", response_class=HTMLResponse, include_in_schema=False)
def register(request: Request, email: str = Form(...), password: str = Form(...), display_name: str = Form(...)):
    email = email.strip().lower()
    with get_session() as s:
        if s.query(User).filter(User.email == email).first():
            return templates.TemplateResponse("auth.html", ctx(request, title="Account", register_error="Email already registered."), status_code=400)
        u = User(email=email, password_hash=bcrypt.hash(password), display_name=display_name.strip())
        s.add(u); s.commit(); s.refresh(u)
    resp = RedirectResponse("/", status_code=303)
    set_user(resp, u.id)
    return resp

@router.post("/auth/login", response_class=HTMLResponse, include_in_schema=False)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    with get_session() as s:
        u = s.query(User).filter(User.email == email).first()
        if not u or not bcrypt.verify(password, u.password_hash):
            return templates.TemplateResponse("auth.html", ctx(request, title="Account", login_error="Invalid credentials."), status_code=400)
    resp = RedirectResponse("/", status_code=303)
    set_user(resp, u.id)
    return resp

@router.post("/auth/logout", include_in_schema=False)
def logout(_: Request):
    resp = RedirectResponse("/", status_code=303)
    clear(resp)
    return resp
