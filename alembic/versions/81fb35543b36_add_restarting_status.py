"""add restarting status

Revision ID: 81fb35543b36
Revises: 08b695623b27
Create Date: 2026-07-13 14:03:14.200739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81fb35543b36'
down_revision: Union[str, Sequence[str], None] = '08b695623b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TYPE deploymentstatus ADD VALUE 'RESTARTING';")


def downgrade() -> None:
    """Downgrade schema."""
    pass
