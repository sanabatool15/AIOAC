"""Sign-in helpers for tests that build their own FastAPI app."""
from app.deps import current_user

DEFAULT = {"user": None}  # set by the autouse fixture in tests/conftest.py


def sign_in(app, user=None):
    """Run every request on `app` as `user` (default: the test's default user), without a cookie."""
    u = user or DEFAULT["user"]
    app.dependency_overrides[current_user] = lambda: u
    return app
