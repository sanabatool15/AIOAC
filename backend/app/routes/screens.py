"""Read-mostly routes behind the History, Model, Usage, Receipts, Share and Activity screens (specs/api.md section D).

All owner-scoped through `owned_project` / `current_user` (404 for anyone else), except the public result link.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..db import Session, get_session
from ..db.tables import Project, User
from ..deps import current_user, get_label_llm, owned_project
from ..integrations.factory import get_storage
from ..services import account, activity, history, model_use, share
from ..services.ratelimit import RateLimiter

router = APIRouter(tags=["screens"])

# per process, in memory. Free routes that cost CPU, and the public link, are limited.
predict_limiter = RateLimiter(120, 60)
batch_limiter = RateLimiter(10, 60)
public_limiter = RateLimiter(60, 60)


# ------------------------------------------------------------------ history and activity

@router.get("/projects/{pid}/history")
def project_history(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    return history.project_history(s, p)


@router.get("/projects/{pid}/activity")
def project_activity(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    return activity.activity(s, p)


# ------------------------------------------------------------------ the trained model

class PredictIn(BaseModel):
    record: dict


class BatchIn(BaseModel):
    csv_text: str


def _limit(limiter: RateLimiter, key: str) -> None:
    if not limiter.allow(key):
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")


def _guard(call):
    try:
        return call()
    except model_use.NoModel as e:
        raise HTTPException(404, str(e))
    except model_use.BadInput as e:
        raise HTTPException(400, str(e))
    except model_use.ModelUnusable as e:
        raise HTTPException(409, str(e))


@router.get("/projects/{pid}/model")
def model_info(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session), label_llm=Depends(get_label_llm)):
    return model_use.describe(s, get_storage(), p, label_llm)


@router.post("/projects/{pid}/predict")
def predict(pid: str, body: PredictIn, p: Project = Depends(owned_project), s: Session = Depends(get_session),
            user: User = Depends(current_user)):
    _limit(predict_limiter, user.id)
    return _guard(lambda: model_use.predict_one(s, get_storage(), p, body.record))


@router.post("/projects/{pid}/predict-batch")
def predict_batch(pid: str, body: BatchIn, p: Project = Depends(owned_project), s: Session = Depends(get_session),
                  user: User = Depends(current_user)):
    _limit(batch_limiter, user.id)
    return _guard(lambda: model_use.predict_batch(s, get_storage(), p, body.csv_text))


@router.get("/projects/{pid}/model/download")
def model_download(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    data, sklearn_version = _guard(lambda: model_use.download(s, get_storage(), p))
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="model-{p.id[:8]}.joblib"',
                             "X-Requires-Scikit-Learn": sklearn_version,
                             "X-Model-Note": "Open with joblib.load using the scikit-learn version in X-Requires-Scikit-Learn."})


# ------------------------------------------------------------------ account

@router.get("/account/usage")
def account_usage(s: Session = Depends(get_session), user: User = Depends(current_user)):
    return account.usage(s, user)


@router.get("/account/payments")
def account_payments(s: Session = Depends(get_session), user: User = Depends(current_user)):
    return account.receipts(s, user)


# ------------------------------------------------------------------ sharing (owner side)

@router.post("/projects/{pid}/share")
def share_create(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    v = share.create(s, p)
    return {"token": v["token"], "url_path": v["url_path"], "created_at": v["created_at"]}


@router.get("/projects/{pid}/share")
def share_status(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    v = share.status(s, p)
    return {"enabled": v["enabled"], "token": v["token"], "created_at": v["created_at"]}


@router.delete("/projects/{pid}/share")
def share_revoke(pid: str, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    share.revoke(s, p)
    return {"enabled": False}


# ------------------------------------------------------------------ sharing (PUBLIC, no login). HUMAN REVIEW.

@router.get("/public/results/{token}")
def public_result(token: str, request: Request, s: Session = Depends(get_session)):
    _limit(public_limiter, request.client.host if request.client else "unknown")
    out = share.public_result(s, token) if 20 <= len(token) <= 200 else None
    if out is None:
        raise HTTPException(404, "result not found")
    return out
