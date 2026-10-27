"""Gate for the real-service tests. They run only for `RUN_REAL=1 pytest tests/real -v -s` (see tests/conftest.py,
which then keeps the developer's real .env instead of isolating it)."""
import os

import pytest


@pytest.fixture(scope="session")
def real_settings():
    if os.environ.get("RUN_REAL") != "1" and os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("real-service test: set RUN_REAL=1 and run `RUN_REAL=1 pytest tests/real -v -s`")
    if os.environ.get("AIOAC_TEST_ISOLATED") == "1":
        pytest.skip("this run is isolated from the real .env; run only the real folder: RUN_REAL=1 pytest tests/real")
    from app.config import settings
    return settings


def need(value, name: str):
    if not value:
        pytest.skip(f"{name} is not set in .env")
