"""Proves: DATABASE_URL in .env points at a reachable database and the tables can be created there.

Read-only in effect: one SELECT 1, plus create_all run inside a transaction that is rolled back (nothing persists).
Run: RUN_REAL=1 pytest tests/real/test_database.py -v -s
"""
from sqlalchemy import text


def test_database_reachable_and_schema_creatable(real_settings):
    from app.db import Base, build_engine
    import app.db.tables  # noqa: F401  (registers the tables on Base.metadata)

    engine = build_engine(real_settings.database_url)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            assert conn.execute(text("SELECT 1")).scalar() == 1
            Base.metadata.create_all(conn)  # inside the transaction; rolled back below
            print("database ok:", engine.dialect.name)
        finally:
            trans.rollback()
