"""add follower enum to connection type

Revision ID: 3f5d9d2f0a1b
Revises: 8f02c650557a
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3f5d9d2f0a1b'
down_revision: Union[str, Sequence[str], None] = '8f02c650557a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE connectiontypeenum ADD VALUE IF NOT EXISTS 'FOLLOWER'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enum types easily.
    pass
