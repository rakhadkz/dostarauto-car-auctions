"""Add bid_step to auctions

Revision ID: 004
Revises: 003
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "auctions",
        sa.Column(
            "bid_step",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="100000",
        ),
    )


def downgrade() -> None:
    op.drop_column("auctions", "bid_step")
