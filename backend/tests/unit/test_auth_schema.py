"""The login tables and columns compile for Postgres (no connection), and the init command hides the password."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import Base
from app.db.init import masked_url
from app.db.tables import Project, User


def test_schema_compiles_for_postgres_including_the_new_columns():
    ddl = {t.name: str(CreateTable(t).compile(dialect=postgresql.dialect())) for t in Base.metadata.sorted_tables}
    assert "organizations" in ddl
    assert "password_hash VARCHAR NOT NULL" in ddl["users"] and "email VARCHAR NOT NULL" in ddl["users"]
    assert User.__table__.c.email.unique and any(i.unique for i in User.__table__.indexes if i.name == "ix_users_email")
    assert "REFERENCES organizations (id)" in ddl["users"] and "REFERENCES organizations (id)" in ddl["projects"]
    assert "REFERENCES users (id)" in ddl["projects"]
    for t in (User.__table__, Project.__table__):
        for ix in t.indexes:
            str(CreateIndex(ix).compile(dialect=postgresql.dialect()))
    assert {"ix_projects_org_user", "ix_projects_user_id", "ix_users_email", "ix_users_org_id"} <= {i.name for t in (User.__table__, Project.__table__) for i in t.indexes}


def test_organizations_come_before_users_and_projects_in_create_order():
    names = [t.name for t in Base.metadata.sorted_tables]
    assert names.index("organizations") < names.index("users") < names.index("projects")


def test_init_masks_the_password():
    shown = masked_url("postgresql://postgres.abc:SuperSecret123@aws-0-eu.pooler.supabase.com:6543/postgres")
    assert "SuperSecret123" not in shown and "***" in shown and "aws-0-eu.pooler.supabase.com" in shown
