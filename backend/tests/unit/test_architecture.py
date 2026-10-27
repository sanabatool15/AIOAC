"""Enforces the folder rules: only app/db and app/repositories touch the database; app/ never uses doubles/."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
ALLOWED = {"db", "repositories"}
FORBIDDEN = re.compile(r"sqlalchemy|session\.(execute|query|add|commit|flush|scalar|scalars|delete|refresh|rollback|get)\b|\bselect\(")


def _files():
    for p in APP.rglob("*.py"):
        if p.relative_to(APP).parts[0] not in ALLOWED:
            yield p


def test_no_database_access_outside_db_and_repositories():
    bad = [f"{p.relative_to(APP)}:{n}: {line.strip()}" for p in _files()
           for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if FORBIDDEN.search(line)]
    assert not bad, "database access outside app/db and app/repositories:\n" + "\n".join(bad)


def test_app_never_imports_doubles():
    bad = [str(p.relative_to(APP)) for p in APP.rglob("*.py")
           if re.search(r"^\s*(from|import)\s+(\.+|app\.)?doubles\b", p.read_text(encoding="utf-8"), re.M)]
    assert not bad, f"app imports doubles: {bad}"


def test_removed_folders_stay_removed():
    for name in ("providers", "jobs", "models"):
        assert not (APP / name).exists(), f"app/{name} should not exist"
