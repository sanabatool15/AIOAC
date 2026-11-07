"""Postgres INTEGER is 32-bit. SQLite accepts bigger numbers, so tests on SQLite never caught a too-big bound."""
from app.services.agent import memory


def test_no_limit_seq_fits_postgres_integer():
    assert 0 < memory._NO_LIMIT_SEQ <= 2**31 - 1
