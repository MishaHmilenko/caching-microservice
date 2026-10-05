"""Create payload tables.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payloads",
        sa.Column("id", sa.CHAR(length=64), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transformed_strings",
        sa.Column("source_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("source_hash"),
    )


def downgrade() -> None:
    op.drop_table("transformed_strings")
    op.drop_table("payloads")
