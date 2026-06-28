"""Auth: session cookie + argon2 password hashing (T010, contracts/http-api.md).

v1 uses a signed session cookie. Session = base64(user_id); signed with secret_key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.db import get_db
from src.models.entities import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
_hasher = PasswordHasher()


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def make_session_cookie(user_id: uuid.UUID) -> str:
    payload = json.dumps({"uid": str(user_id)})
    b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{b64}.{_sign(b64)}"


def parse_session_cookie(cookie: str) -> uuid.UUID | None:
    try:
        b64, sig = cookie.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(b64)):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(b64))
        return uuid.UUID(payload["uid"])
    except Exception:
        return None


def current_user(request: Request) -> User:
    cookie = request.cookies.get("session")
    if not cookie:
        raise HTTPException(status_code=401, detail="not authenticated")
    uid = parse_session_cookie(cookie)
    if uid is None:
        raise HTTPException(status_code=401, detail="invalid session")
    db: Session = request.state.db
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    request.state.db = db
    return current_user(request)


class Creds(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(creds: Creds, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter_by(email=creds.email).first():
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=creds.email, password_hash=_hasher.hash(creds.password))
    db.add(user)
    db.commit()
    return {"user_id": str(user.id)}


@router.post("/login")
def login(creds: Creds, db: Session = Depends(get_db)) -> JSONResponse:
    user = db.query(User).filter_by(email=creds.email).first()
    try:
        if user is None:
            _hasher.hash("dummy")  # equalize timing
            raise VerifyMismatchError
        _hasher.verify(user.password_hash, creds.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="invalid credentials")
    resp = JSONResponse(content={"ok": True})
    resp.set_cookie(
        "session", make_session_cookie(user.id), httponly=True, samesite="lax"
    )
    return resp


@router.post("/logout")
def logout() -> JSONResponse:
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("session")
    return resp
