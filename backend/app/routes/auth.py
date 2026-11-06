"""Sign up, sign in, sign out. The session lives in an httpOnly cookie holding a signed token (services/auth.py)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..config import settings
from ..db import Session, get_session
from ..db.tables import User
from ..deps import current_user
from ..services import auth

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Credentials(BaseModel):
    email: str = Field(max_length=254, pattern=_EMAIL)
    password: str = Field(min_length=auth.MIN_PASSWORD, max_length=200)


def user_view(u: User) -> dict:
    return {"id": u.id, "email": u.email, "org_id": u.org_id}


def _set_cookie(response: Response, user: User) -> None:
    response.set_cookie(settings.cookie_name, auth.issue_token(user), max_age=settings.jwt_ttl_minutes * 60, httponly=True,
                        secure=settings.cookie_secure, samesite=settings.cookie_samesite, path="/")


def _not_set_up() -> HTTPException:
    return HTTPException(503, "login is not set up")


@router.post("/signup")
def signup(body: Credentials, response: Response, s: Session = Depends(get_session)):
    try:
        user = auth.signup(s, body.email, body.password)
    except auth.NotConfigured:
        raise _not_set_up()
    except auth.EmailTaken as e:
        raise HTTPException(409, str(e))
    _set_cookie(response, user)
    return {"user": user_view(user)}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, s: Session = Depends(get_session)):
    try:
        user = auth.login(s, body.email, body.password, ip=request.client.host if request.client else "")
    except auth.NotConfigured:
        raise _not_set_up()
    except auth.BadLogin as e:
        raise HTTPException(401, str(e))
    except auth.TooManyAttempts as e:
        raise HTTPException(429, str(e))
    _set_cookie(response, user)
    return {"user": user_view(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"user": user_view(user)}


@router.post("/demo")
def demo(response: Response, s: Session = Depends(get_session)):
    """For the demo video only. Off (404) unless DEMO_LOGIN_ENABLED=true."""
    if not settings.demo_login_enabled:
        raise HTTPException(404, "Not Found")
    try:
        user = auth.demo_login(s)
    except auth.NotConfigured:
        raise _not_set_up()
    _set_cookie(response, user)
    return {"user": user_view(user)}
