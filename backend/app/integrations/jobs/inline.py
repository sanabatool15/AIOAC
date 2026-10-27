import threading
from typing import Callable


class InlineJobRunner:
    """Runs the job in this process. threaded=False runs it before enqueue() returns (tests, no network).
    threaded=True runs it in a background thread so the HTTP request returns at once (the default for the
    local demo)."""

    stale_after_seconds = 0  # in-process: after a restart every `running` run is dead

    def __init__(self, execute: Callable[[str], None], threaded: bool = False):
        self.execute, self.threaded = execute, threaded
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def _work(self, run_id: str) -> None:
        try:
            self.execute(run_id)
        finally:
            with self._lock:
                self._active.discard(run_id)

    def enqueue(self, run_id: str) -> None:
        with self._lock:
            self._active.add(run_id)
        if self.threaded:
            threading.Thread(target=self._work, args=(run_id,), daemon=True, name=f"train-{run_id[:8]}").start()
        else:
            self._work(run_id)

    def is_active(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._active
