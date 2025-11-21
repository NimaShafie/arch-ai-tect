# server/core/session.py
from typing import Dict, Any, Optional, List
from itsdangerous import URLSafeSerializer, BadSignature
from fastapi import Request, Response
from .config import AW_SECRET, SESSION_COOKIE
from ..db import get_session
from ..models import User

_signer = URLSafeSerializer(AW_SECRET, salt="aw-session")

def _payload(request: Request) -> Dict[str, Any]:
    tok = request.cookies.get(SESSION_COOKIE)
    if not tok:
        return {}
    try:
        return _signer.loads(tok)
    except BadSignature:
        return {}

def _write(resp: Response, payload: Dict[str, Any]) -> None:
    resp.set_cookie(
        SESSION_COOKIE,
        _signer.dumps(payload),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
    )

def set_user(resp: Response, user_id: int) -> None:
    _write(resp, {"uid": user_id})

def clear(resp: Response) -> None:
    resp.delete_cookie(SESSION_COOKIE)

def current_user(request: Request) -> Optional[User]:
    p = _payload(request)
    uid = p.get("uid")
    if not uid:
        return None
    with get_session() as s:
        return s.get(User, uid)

def guest_temps(request: Request) -> List[str]:
    p = _payload(request)
    t = p.get("temps")
    return t if isinstance(t, list) else []

def add_guest_temp(resp: Response, request: Request, slug: str) -> None:
    p = _payload(request)
    t = p.get("temps") or []
    if slug not in t:
        t.append(slug)
    p.pop("uid", None)
    p["guest"] = True
    p["temps"] = t
    _write(resp, p)

def del_guest_temp(resp: Response, request: Request, slug: str) -> None:
    p = _payload(request)
    t = p.get("temps") or []
    if slug in t:
        t.remove(slug)
    p["temps"] = t
    _write(resp, p)
