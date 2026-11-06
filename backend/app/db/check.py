"""Compare the live database with the models, and add what is missing (`python -m app.db.init --check | --upgrade`).

There are no migrations. `create_all` only creates missing tables, so a database made by an older version of the app
lacks the columns added since. This module reports the gap (read-only) and can fill it, adding only:
missing tables, missing columns (nullable, or NOT NULL with a safe default), missing indexes and unique indexes.
It never drops, renames or alters an existing column and never touches rows.
"""
from dataclasses import dataclass, field

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Table, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.schema import CreateTable

from . import tables  # noqa: F401  (importing registers the tables)
from .session import Base


@dataclass
class Report:
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: list[tuple[str, Column]] = field(default_factory=list)
    missing_indexes: list[tuple[str, str, tuple[str, ...], bool]] = field(default_factory=list)  # table, name, cols, unique
    missing_uniques: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # differences that do not block (types, nullability)

    @property
    def clean(self) -> bool:
        return not (self.missing_tables or self.missing_columns or self.missing_indexes or self.missing_uniques)


def _family(t) -> str:
    """Coarse type family, so VARCHAR vs TEXT or INTEGER vs BIGINT is not reported."""
    if isinstance(t, Boolean):
        return "bool"
    if isinstance(t, Integer):
        return "int"
    if isinstance(t, Float):
        return "float"
    if isinstance(t, DateTime):
        return "datetime"
    if isinstance(t, String):
        return "str"
    try:
        return {bool: "bool", int: "int", float: "float", str: "str"}.get(t.python_type, type(t).__name__.lower())
    except NotImplementedError:
        return type(t).__name__.lower()


def _model_uniques(table: Table) -> list[tuple[str, ...]]:
    out = []
    for c in table.constraints:
        if c.__class__.__name__ == "UniqueConstraint":
            out.append(tuple(col.name for col in c.columns))
    for i in table.indexes:
        if i.unique:
            out.append(tuple(col.name for col in i.columns))
    return list(dict.fromkeys(out))


def compare(engine: Engine) -> Report:
    insp = inspect(engine)
    live_tables = set(insp.get_table_names())
    rep = Report()
    for name, table in Base.metadata.tables.items():
        if name not in live_tables:
            rep.missing_tables.append(name)
            continue
        live_cols = {c["name"]: c for c in insp.get_columns(name)}
        for col in table.columns:
            live = live_cols.get(col.name)
            if live is None:
                rep.missing_columns.append((name, col))
                continue
            if _family(live["type"]) != _family(col.type):
                rep.notes.append(f"{name}.{col.name}: type differs (live {live['type']}, model {col.type})")
            if not live["nullable"] and col.nullable:
                rep.notes.append(f"{name}.{col.name}: NOT NULL in the database but nullable in the model (inserts may fail)")
        live_idx = {i["name"]: i for i in insp.get_indexes(name)}
        live_unique = {tuple(u["column_names"]) for u in insp.get_unique_constraints(name)}
        live_unique |= {tuple(i["column_names"]) for i in live_idx.values() if i.get("unique")}
        pk = tuple(insp.get_pk_constraint(name).get("constrained_columns") or ())
        if pk:
            live_unique.add(pk)
        for idx in table.indexes:
            if idx.name not in live_idx:
                cols = tuple(c.name for c in idx.columns)
                if idx.unique and cols in live_unique:
                    continue
                rep.missing_indexes.append((name, idx.name, cols, bool(idx.unique)))
        indexed = {i[2] for i in rep.missing_indexes if i[0] == name and i[3]}
        for cols in _model_uniques(table):
            if cols not in live_unique and cols not in indexed:
                rep.missing_uniques.append((name, cols))
    return rep


def _default_literal(col: Column) -> str | None:
    """A safe SQL default for a NOT NULL column, or None when there is none (then the column is added nullable)."""
    d = col.default
    if d is not None and getattr(d, "is_scalar", False):
        v = d.arg
        if isinstance(v, bool):
            return "false" if not v else "true"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
    if col.server_default is not None and getattr(col.server_default, "arg", None) is not None:
        arg = col.server_default.arg
        if isinstance(arg, str):
            return "'" + arg.replace("'", "''") + "'"
    if isinstance(col.type, Boolean):
        return "false"
    if isinstance(col.type, (Integer, Float)):
        return "0"
    if isinstance(col.type, String):
        return "''"
    return None


# Never invent a value for these: old rows stay NULL (an old user has no password and must sign up again).
KEEP_NULL = {("users", "password_hash")}


def column_sql(engine: Engine, table: str, col: Column) -> str:
    d = engine.dialect
    q = d.identifier_preparer.quote
    ine = "IF NOT EXISTS " if d.name == "postgresql" else ""
    sql = f"ALTER TABLE {q(table)} ADD COLUMN {ine}{q(col.name)} {col.type.compile(dialect=d)}"
    keep_null = (table, col.name) in KEEP_NULL
    lit = None if col.nullable or keep_null else _default_literal(col)
    if lit is not None:
        if d.name == "sqlite" and lit in ("true", "false"):
            lit = "1" if lit == "true" else "0"
        sql += f" DEFAULT {lit} NOT NULL"
    return sql


def index_sql(engine: Engine, table: str, name: str, cols: tuple[str, ...], unique: bool) -> str:
    q = engine.dialect.identifier_preparer.quote
    return (f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS {q(name)} ON {q(table)} ({', '.join(q(c) for c in cols)})")


def _has_duplicates(conn: Connection, table: str, cols: tuple[str, ...]) -> bool:
    q = conn.dialect.identifier_preparer.quote
    cl = ", ".join(q(c) for c in cols)
    nn = " AND ".join(f"{q(c)} IS NOT NULL" for c in cols)
    row = conn.execute(text(f"SELECT 1 FROM {q(table)} WHERE {nn} GROUP BY {cl} HAVING COUNT(*) > 1 LIMIT 1")).first()
    return row is not None


def plan(engine: Engine, rep: Report) -> list[tuple[str, str, object]]:
    """Ordered steps: (kind, printable sql, payload). Kinds: table, column, index, unique."""
    steps: list[tuple[str, str, object]] = []
    for name in rep.missing_tables:
        t = Base.metadata.tables[name]
        steps.append(("table", str(CreateTable(t).compile(dialect=engine.dialect)).strip(), t))
    for table, col in rep.missing_columns:
        steps.append(("column", column_sql(engine, table, col), (table, col)))
    seen = set()
    for table, name, cols, unique in rep.missing_indexes:
        if table in rep.missing_tables:
            continue  # create_all makes the table's own indexes
        seen.add((table, cols))
        steps.append(("unique" if unique else "index", index_sql(engine, table, name, cols, unique), (table, cols)))
    for table, cols in rep.missing_uniques:
        if table in rep.missing_tables or (table, cols) in seen:
            continue
        steps.append(("unique", index_sql(engine, table, f"uq_{table}_{'_'.join(cols)}", cols, True), (table, cols)))
    return steps


def format_report(rep: Report) -> list[str]:
    lines = []
    if rep.clean:
        lines.append("OK: every model table, column and index exists in the database.")
    for t in rep.missing_tables:
        lines.append(f"MISSING TABLE  {t}")
    for t, c in rep.missing_columns:
        lines.append(f"MISSING COLUMN {t}.{c.name}  {c.type}  {'NULL' if c.nullable else 'NOT NULL'}")
    for t, n, cols, u in rep.missing_indexes:
        lines.append(f"MISSING {'UNIQUE ' if u else ''}INDEX {n} on {t}({', '.join(cols)})")
    for t, cols in rep.missing_uniques:
        lines.append(f"MISSING UNIQUE {t}({', '.join(cols)})")
    for n in rep.notes:
        lines.append(f"note: {n}")
    return lines


def upgrade(engine: Engine, execute: bool, out=print) -> int:
    """Print every statement; run them in one transaction only when execute is true. Returns an exit code."""
    rep = compare(engine)
    for line in format_report(rep):
        out(line)
    steps = plan(engine, rep)
    if not steps:
        out("nothing to upgrade.")
        return 0
    guidance = []
    if any(c.name == "password_hash" for t, c in rep.missing_columns if t == "users"):
        guidance.append("users.password_hash will be NULL for existing users: they cannot log in and must sign up again.")
    try:
        with engine.begin() as conn:
            for kind, sql, payload in steps:
                if kind == "unique" and execute:
                    table, cols = payload
                    if _has_duplicates(conn, table, cols):
                        out(f"-- SKIPPED (duplicates exist): {sql}")
                        guidance.append(f"{table}({', '.join(cols)}) has duplicate values: remove the duplicates by hand, "
                                        "then run --upgrade --yes again.")
                        continue
                out(sql + ";")
                if not execute:
                    continue
                if kind == "table":
                    Base.metadata.create_all(conn, tables=[payload])
                else:
                    conn.execute(text(sql))
    except Exception as exc:  # noqa: BLE001
        out(f"ERROR, rolled back: {type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}")
        return 1
    out("done." if execute else "dry run: nothing was executed. Add --yes to run the statements above.")
    for g in guidance:
        out(f"note: {g}")
    return 0
