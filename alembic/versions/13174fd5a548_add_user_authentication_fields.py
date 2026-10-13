"""Add user authentication fields

Revision ID: 13174fd5a548
Revises: 6d4ad3446ade
Create Date: 2026-10-12 19:14:18.385671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13174fd5a548'
down_revision: Union[str, Sequence[str], None] = '6d4ad3446ade'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'customer'"),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('customer', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_role_valid",
        "users",
        type_="check",
    )

    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
    # ### end Alembic commands ###
