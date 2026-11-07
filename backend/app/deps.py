from fastapi import Depends, HTTPException, Request
from .config import settings
from .db import Session, get_session
from .db.tables import Project, User
from .integrations.factory import get_dataset_source, get_llm, llm_configured, get_job_runner, get_payment_provider, get_storage, get_training_backend
from .repositories import projects as projects_repo
from .services import auth
from .services.agent.tools import ToolContext


def get_ctx_factory(session: Session = Depends(get_session)):
    def make(project, approved=frozenset()) -> ToolContext:
        return ToolContext(session=session, project=project, storage=get_storage(), provider=get_payment_provider(),
                           provider_name=settings.payment_provider, backend=get_training_backend(), source=get_dataset_source(), approved=set(approved), runner=get_job_runner())
    return make


def get_llm_client():
    """The model client for /chat. Without a real key the API answers 503 with a plain message instead of a 200 error reply."""
    if not llm_configured():
        raise HTTPException(503, "The AI assistant is not set up on this server yet (no model key is configured). "
                                 "You can still use the screens that do not need chat.")
    return get_llm()


def get_label_llm():
    """A small model for plain-English column labels, or None when no model is configured. Never an error:
    labels are a nice-to-have, so the Model tab simply shows the raw column names without them."""
    try:
        if not llm_configured():
            return None
        return get_llm(settings.label_model.strip() or None, timeout=settings.label_timeout_s)
    except Exception:
        return None


def current_user(request: Request, s: Session = Depends(get_session)) -> User:
    """The signed-in user, from the session cookie. 503 if login is not set up, 401 if there is no valid session."""
    if not auth.configured():
        raise HTTPException(503, "login is not set up")
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(401, "please sign in")
    try:
        return auth.user_for_token(s, token)
    except auth.BadToken:
        raise HTTPException(401, "please sign in")


def owned_project(pid: str, s: Session = Depends(get_session), user: User = Depends(current_user)) -> Project:
    """The project, only if it belongs to the signed-in user AND their org. Anything else is 404, never 403,
    so nobody can learn whether another user's project exists."""
    p = projects_repo.get_owned(s, pid, user.id, user.org_id)
    if p is None:
        raise HTTPException(404, "project not found")
    return p
