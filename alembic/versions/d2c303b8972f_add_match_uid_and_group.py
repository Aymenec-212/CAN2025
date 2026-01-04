"""add match uid and group

Revision ID: d2c303b8972f
Revises: 835cece4e486
Create Date: 2026-01-01 17:04:45.688684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2c303b8972f'
down_revision: Union[str, Sequence[str], None] = '835cece4e486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("uid", sa.String(), nullable=True))
    op.add_column("matches", sa.Column("group", sa.String(length=1), nullable=True))
    op.execute("UPDATE matches SET uid = CONCAT('CAN2025:LEGACY:', id) WHERE uid IS NULL")
    op.create_unique_constraint("uq_matches_uid","matches",["uid"])
    op.create_index("ix_matches_group","matches",["group"])
    op.alter_column("matches", "uid", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_matches_group", table_name="matches")
    op.drop_constraint("uq_matches_uid", "matches", type_="unique")
    op.drop_column("matches", "group")
    op.drop_column("matches", "uid")
