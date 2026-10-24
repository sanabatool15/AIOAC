from functools import lru_cache

from ..config import settings
from .base import JobRunner
from .inline import InlineJobRunner


@lru_cache
def get_job_runner() -> JobRunner:
    if settings.job_runner == "inngest":
        from .inngest_runner import InngestJobRunner  # imported here so the inline default needs no extra package

        return InngestJobRunner()
    from .worker import run_job

    return InlineJobRunner(run_job, threaded=True)
