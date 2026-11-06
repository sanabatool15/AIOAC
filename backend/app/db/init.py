"""Create the tables on the configured database: `python -m app.db.init`.

Use it once on a new database (for example Supabase). It only creates tables that are missing; it never drops or
changes existing ones, so after a schema change on an existing database you must delete the database (no migrations).
The password in DATABASE_URL is never printed.
"""
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from ..config import settings
from . import tables  # noqa: F401  (importing registers the tables)
from .session import Base, engine


def masked_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def main() -> int:
    print(f"database: {masked_url(settings.database_url)}")
    print(f"dialect: {engine.dialect.name}")
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(engine)
    after = set(inspect(engine).get_table_names())
    created = sorted(after - before)
    print("created tables: " + (", ".join(created) if created else "(none, all already existed)"))
    print("existing tables: " + (", ".join(sorted(before & set(Base.metadata.tables))) or "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
