"""add_starting_removed_to_deployment_status

Revision ID: 1aa71f47daeb
Revises: 81fb35543b36
Create Date: 2026-07-13 23:36:19.910997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1aa71f47daeb'
down_revision: Union[str, Sequence[str], None] = '81fb35543b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires ADD VALUE to be outside a transaction block.
    # Alembic's op.execute with the connection directly handles this fine.
    op.execute("ALTER TYPE deploymentstatus ADD VALUE IF NOT EXISTS 'STARTING'")
    op.execute("ALTER TYPE deploymentstatus ADD VALUE IF NOT EXISTS 'REMOVED'")


def downgrade() -> None:
    # Postgres does not support removing individual enum values without
    # recreating the type. Downgrade is intentionally a no-op — if you need
    # to roll back, drop and recreate the enum manually.
    pass
