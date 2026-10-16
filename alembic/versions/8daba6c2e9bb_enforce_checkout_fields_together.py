"""Enforce checkout fields together

Revision ID: 8daba6c2e9bb
Revises: 456052882d9d
Create Date: 2026-10-16 18:22:24.337492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8daba6c2e9bb'
down_revision: Union[str, Sequence[str], None] = '456052882d9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
    "ck_orders_checkout_fields_together",
    "orders",
    """
    (idempotency_key IS NULL AND checkout_fingerprint IS NULL)
    OR
    (idempotency_key IS NOT NULL AND checkout_fingerprint IS NOT NULL)
    """,
)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
    "ck_orders_checkout_fields_together",
    "orders",
    type_="check",
)
