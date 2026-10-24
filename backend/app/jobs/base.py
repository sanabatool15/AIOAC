from typing import Protocol


class JobRunner(Protocol):
    """Runs a training job (by run id) outside the HTTP request."""

    stale_after_seconds: int  # how long a silent `running` run waits before crash recovery may fail it

    def enqueue(self, run_id: str) -> None:
        """Hand the run to a worker and return at once. Raises if the job could not be queued."""
        ...

    def is_active(self, run_id: str) -> bool:
        """True if this process knows a live worker for the run. Runners that cannot know return False
        and rely on the heartbeat (stale_after_seconds) instead."""
        ...
