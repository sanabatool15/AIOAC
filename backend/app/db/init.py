"""Create the tables on the configured database: `python -m app.db.init`.

`--check` compares the live database with the models (read-only, exit 1 if something is missing).
`--upgrade` prints the SQL that adds missing columns, indexes and tables; add `--yes` to run it (see check.py).

Use it once on a new database (for example Supabase). It only creates tables that are missing; it never drops or
changes existing ones, so after a schema change on an existing database you must delete the database (no migrations).
The password in DATABASE_URL is never printed.
"""
import sys

from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from ..config import settings
from . import check, tables  # noqa: F401  (importing registers the tables)
from .session import Base, engine


def masked_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def main(argv: list[str] | None = None, eng=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    eng = eng or engine
    print(f"database: {eng.url.render_as_string(hide_password=True)}")
    print(f"dialect: {eng.dialect.name}")
    if "--check" in args:
        rep = check.compare(eng)
        for line in check.format_report(rep):
            print(line)
        return 0 if rep.clean else 1
    if "--upgrade" in args:
        return check.upgrade(eng, execute="--yes" in args)
    before = set(inspect(eng).get_table_names())
    Base.metadata.create_all(eng)
    after = set(inspect(eng).get_table_names())
    created = sorted(after - before)
    print("created tables: " + (", ".join(created) if created else "(none, all already existed)"))
    print("existing tables: " + (", ".join(sorted(before & set(Base.metadata.tables))) or "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
