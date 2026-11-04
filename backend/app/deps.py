from fastapi import Depends, HTTPException
from .config import settings
from .db import Session, get_session
from .integrations.factory import get_dataset_source, get_llm, llm_configured, get_job_runner, get_payment_provider, get_storage, get_training_backend
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
