import json
import math

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from ..config import settings


class Base(DeclarativeBase):
    pass


def _finite(value):
    """Copy of a JSON-ready value in which NaN and infinity (pandas missing values) become None."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


def json_dumps(value) -> str:
    """JSON text for the JSON columns. Python writes NaN as a bare token, SQLite accepts it, but Postgres rejects it
    ('invalid input syntax for type json') and the whole save fails. Strict JSON has null instead, so use that."""
    return json.dumps(_finite(value), allow_nan=False)


def build_engine(database_url: str, pooled: bool | None = None) -> Engine:
    """SQLite by default. For Postgres (for example Supabase) install the extra: pip install -e '.[postgres]'.

    - `postgres://` and `postgresql://` URLs are rewritten to use the psycopg 3 driver.
    - Supabase's pooled connection string (Supavisor, port 6543, transaction mode) cannot keep prepared statements
      or long-lived connections, so for it we turn prepared statements off and let the pooler do the pooling.
    create_engine is lazy: nothing connects until the first query.
    """
    url: URL = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return create_engine(url, connect_args={"check_same_thread": False},  # background worker uses its own session
                             json_serializer=json_dumps)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if pooled is None:
        pooled = url.port == 6543
    if pooled:
        return create_engine(url, poolclass=NullPool, connect_args={"prepare_threshold": None}, json_serializer=json_dumps)
    return create_engine(url, pool_pre_ping=True, json_serializer=json_dumps)


engine = build_engine(settings.database_url, settings.database_pooled)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session
