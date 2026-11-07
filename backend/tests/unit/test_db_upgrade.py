"""`python -m app.db.init --check / --upgrade` on SQLite files made from an old schema, plus Postgres SQL compile."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql

from app.db import check
from app.db.init import main
from app.db.session import Base

OLD_DDL = [
    "CREATE TABLE organizations (id VARCHAR PRIMARY KEY, name VARCHAR, created_at DATETIME)",
    "CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR, created_at DATETIME)",  # no password_hash, org_id, unique
    "CREATE TABLE projects (id VARCHAR PRIMARY KEY, goal VARCHAR, status VARCHAR, created_at DATETIME)",
]


def make_old(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    others = [t for n, t in Base.metadata.tables.items() if n not in ("organizations", "users", "projects")]
    with eng.begin() as c:
        for ddl in OLD_DDL:
            c.execute(text(ddl))
        c.execute(text("INSERT INTO users (id, email) VALUES ('u1', 'a@x.com')"))
    # tables other than the old three are not created: they must be reported missing
    return eng, others


def test_current_schema_is_clean(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    Base.metadata.create_all(eng)
    assert check.compare(eng).clean
    assert main(["--check"], eng) == 0


def test_check_upgrade_check_cycle(tmp_path, capsys):
    eng, _ = make_old(tmp_path)
    assert main(["--check"], eng) == 1
    out = capsys.readouterr().out
    assert "MISSING COLUMN users.password_hash" in out
    assert "MISSING COLUMN users.org_id" in out
    assert "MISSING COLUMN projects.user_id" in out
    assert "MISSING TABLE  payments" in out
    assert "ix_projects_org_user" in out

    assert main(["--upgrade", "--yes"], eng) == 0
    out = capsys.readouterr().out
    assert "ALTER TABLE users ADD COLUMN password_hash" in out
    assert "cannot log in" in out
    assert main(["--check"], eng) == 0
    # existing row kept, password_hash empty
    with eng.connect() as c:
        assert c.execute(text("SELECT email, password_hash FROM users")).one() == ("a@x.com", None)
    idx = {i["name"] for i in inspect(eng).get_indexes("users")}
    assert "ix_users_email" in idx
    # second run changes nothing
    assert main(["--upgrade", "--yes"], eng) == 0
    assert "nothing to upgrade" in capsys.readouterr().out


def test_dry_run_executes_nothing(tmp_path, capsys):
    eng, _ = make_old(tmp_path)
    assert main(["--upgrade"], eng) == 0
    out = capsys.readouterr().out
    assert "ALTER TABLE users ADD COLUMN" in out and "dry run" in out
    assert [c["name"] for c in inspect(eng).get_columns("users")] == ["id", "email", "created_at"]
    assert "payments" not in inspect(eng).get_table_names()


def test_duplicate_emails_block_unique_index(tmp_path, capsys):
    eng, _ = make_old(tmp_path)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (id, email) VALUES ('u2', 'a@x.com')"))
    assert main(["--upgrade", "--yes"], eng) == 0
    out = capsys.readouterr().out
    assert "SKIPPED (duplicates exist)" in out and "duplicate values" in out
    assert main(["--check"], eng) == 1  # still reported
    assert "password_hash" in [c["name"] for c in inspect(eng).get_columns("users")]


def test_error_rolls_back(tmp_path, monkeypatch, capsys):
    eng, _ = make_old(tmp_path)
    real = check.column_sql
    monkeypatch.setattr(check, "column_sql", lambda e, t, c: "ALTER TABLE nope ADD COLUMN x TEXT" if c.name == "org_id" else real(e, t, c))
    assert main(["--upgrade", "--yes"], eng) == 1
    assert "rolled back" in capsys.readouterr().out


def test_postgres_statements_compile_without_connection():
    eng = type("E", (), {"dialect": postgresql.dialect()})()  # only the dialect is used: no connection
    table = Base.metadata.tables["payments"]
    stmts = [check.column_sql(eng, "payments", table.c[n]) for n in ("approve_url", "compute_amount_cents", "state")]
    assert all(s.startswith("ALTER TABLE payments ADD COLUMN IF NOT EXISTS") for s in stmts)
    assert "DEFAULT 'none' NOT NULL" in stmts[2]
    assert check.index_sql(eng, "projects", "ix_projects_org_user", ("org_id", "user_id"), False) == (
        "CREATE INDEX IF NOT EXISTS ix_projects_org_user ON projects (org_id, user_id)")
    assert postgresql.dialect().name == "postgresql"


def test_null_password_hash_means_no_login():
    from app.services.auth import verify_password
    assert verify_password("whatever", None) is False


def test_database_without_column_labels_gets_the_table_added(tmp_path, capsys):
    eng = create_engine(f"sqlite:///{tmp_path / 'nolabels.db'}")
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(text("DROP TABLE column_labels"))
    assert main(["--check"], eng) == 1
    assert "MISSING TABLE  column_labels" in capsys.readouterr().out
    assert main(["--upgrade", "--yes"], eng) == 0
    assert main(["--check"], eng) == 0
    cols = {c["name"] for c in inspect(eng).get_columns("column_labels")}
    assert {"dataset_version_id", "labels", "model", "created_at"} <= cols
    assert any(i["unique"] for i in inspect(eng).get_indexes("column_labels"))
