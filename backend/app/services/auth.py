"""Login: password hashing, session tokens, signup, login and a small failure throttle.

HUMAN REVIEW (secrets handling). Rules kept here:
- Passwords are never stored or logged; only a salted scrypt hash is kept.
- The session token is a signed JWT (HS256) with the user id, the org id and an expiry. The signing key is
  `settings.secret_key`; with no real key, login is "not set up" and nothing is signed.
- Wrong email and wrong password give the same error, and cost about the same time.
"""
import base64
import hashlib
import hmac
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings
from ..db import Session
from ..db.tables import User
from ..repositories import users as users_repo

MIN_PASSWORD = 8
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
_PLACEHOLDERS = ("change-me", "changeme", "your-", "placeholder", "example", "secret-key-here")


class AuthError(Exception):
    pass


class NotConfigured(AuthError):
    pass


class EmailTaken(AuthError):
    pass


class BadLogin(AuthError):
    pass


class TooManyAttempts(AuthError):
    pass


class BadToken(AuthError):
    pass


def configured() -> bool:
    key = settings.secret_key.strip()
    return len(key) >= 16 and not any(p in key.lower() for p in _PLACEHOLDERS)


def _require_configured() -> None:
    if not configured():
        raise NotConfigured("login is not set up")


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt${n}${r}${p}${}${}".format(base64.b64encode(salt).decode(), base64.b64encode(digest).decode(), **_SCRYPT)


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


_DUMMY_HASH = hash_password("not-a-real-password")  # compared when the email is unknown, so timing does not reveal it


# ---------------------------------------------------------------- tokens

def issue_token(user: User) -> str:
    _require_configured()
    now = datetime.now(timezone.utc)
    claims = {"sub": user.id, "org": user.org_id, "iat": now, "exp": now + timedelta(minutes=settings.jwt_ttl_minutes)}
    return jwt.encode(claims, settings.secret_key, algorithm="HS256")


def read_token(token: str) -> dict:
    _require_configured()
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"], options={"require": ["exp", "sub", "org"]})
    except jwt.PyJWTError:
        raise BadToken("please sign in")
    return claims


def user_for_token(session: Session, token: str) -> User:
    """The user a valid token names, and only if the org in the token is still the user's org."""
    claims = read_token(token)
    user = users_repo.get(session, claims["sub"])
    if user is None or user.org_id != claims["org"]:
        raise BadToken("please sign in")
    return user


# ---------------------------------------------------------------- throttle (in memory, per process)

_failures: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def _window() -> float:
    return settings.login_window_minutes * 60.0


def _recent(key: tuple[str, str]) -> list[float]:
    cutoff = time.monotonic() - _window()
    kept = [t for t in _failures.get(key, []) if t > cutoff]
    if kept:
        _failures[key] = kept
    else:
        _failures.pop(key, None)
    return kept


def reset_throttle() -> None:
    with _lock:
        _failures.clear()


# ---------------------------------------------------------------- signup and login

def signup(session: Session, email: str, password: str) -> User:
    _require_configured()
    email = users_repo.normalize(email)
    user = users_repo.create_with_org(session, email, hash_password(password), org_name=f"{email} (personal)")
    if user is None:
        raise EmailTaken("that email is already registered")
    return user


def login(session: Session, email: str, password: str, ip: str = "") -> User:
    _require_configured()
    key = (users_repo.normalize(email), ip)
    with _lock:
        if len(_recent(key)) >= settings.login_max_failures:
            raise TooManyAttempts("too many attempts; please wait a few minutes and try again")
    user = users_repo.by_email(session, email)
    ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        with _lock:
            _failures.setdefault(key, []).append(time.monotonic())
        raise BadLogin("wrong email or password")
    with _lock:
        _failures.pop(key, None)
    return user


def demo_login(session: Session) -> User:
    """The fixed demo user, created on first use. Only reachable when DEMO_LOGIN_ENABLED=true (see routes/auth.py).
    Its password is random and never shown, so the account cannot be signed into through /auth/login."""
    _require_configured()
    email = "demo@aioac.example"
    user = users_repo.by_email(session, email)
    if user is None:
        user = users_repo.create_with_org(session, email, hash_password(base64.b64encode(os.urandom(24)).decode()), "Demo")
        user = user or users_repo.by_email(session, email)
    return user
