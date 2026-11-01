"""The API's reader role may read which migration is installed.

Revision ID: 0003
Revises: 0002

``/health/ready`` (protocols/observability-and-operations.md) must say whether the database is on the revision the code
expects. Alembic keeps the installed revision in ``public.alembic_version`` (one row, an id like ``0003``), which only the
migrator could read. This grants SELECT on that one table to ``app_reader``; nothing else changes, and no other role gets it.
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON public.alembic_version TO app_reader")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON public.alembic_version FROM app_reader")
