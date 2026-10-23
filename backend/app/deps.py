from fastapi import Depends
from sqlalchemy.orm import Session

from .config import settings
from .db import get_session
from .providers.llm import get_llm
from .providers.payments import get_payment_provider
from .providers.storage import get_storage
from .providers.training import get_training_backend
from .services.agent.tools import ToolContext


def get_ctx_factory(session: Session = Depends(get_session)):
    def make(project, approved=frozenset()) -> ToolContext:
        return ToolContext(session=session, project=project, storage=get_storage(), provider=get_payment_provider(),
                           provider_name=settings.payment_provider, backend=get_training_backend(), approved=set(approved))
    return make
