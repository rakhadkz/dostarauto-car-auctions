"""Add bank_account to users

Revision ID: 002
Revises: 001
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("bank_account", sa.String(34), nullable=False, server_default=""),
    )
    # Remove the server default after adding — it was only needed to fill existing rows
    op.alter_column("users", "bank_account", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "bank_account")
