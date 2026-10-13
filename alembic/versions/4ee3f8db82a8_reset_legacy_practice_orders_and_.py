"""Reset legacy practice orders and restore stock

Revision ID: 4ee3f8db82a8
Revises: 0dd557420bb2
Create Date: 2026-10-13 20:18:34.272294

"""
from typing import Sequence, Union

from alembic import op
from alembic import context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ee3f8db82a8'
down_revision: Union[str, Sequence[str], None] = '0dd557420bb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Fail promptly if another session is holding conflicting locks.
    connection.execute(
        sa.text("SET LOCAL lock_timeout = '5s'")
    )

    # Keep the checked data stable throughout the reset.
    connection.execute(
        sa.text(
            """
            LOCK TABLE orders, order_items, products
            IN ACCESS EXCLUSIVE MODE
            """
        )
    )

    item_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM order_items")
    ).scalar_one()

    if item_count != 0:
        raise RuntimeError(
            "Expected order_items to be empty. "
            "Stop and inspect the existing data before resetting."
        )

    order_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM orders")
    ).scalar_one()

    if order_count == 0:
        return

    # Require an explicit flag before deleting existing practice data.
    arguments = context.get_x_argument(
    as_dictionary=True
)

    if arguments.get("reset_practice_orders") != "true":
        raise RuntimeError(
            "This migration deletes old practice orders. "
            "Run with -x reset_practice_orders=true "
            "only on the intended development database."
        )

    # Restore the stock deducted by the old order API.
    connection.execute(
        sa.text(
            """
            UPDATE products AS p
            SET stock = p.stock + ordered.total_quantity
            FROM (
                SELECT
                    product_id,
                    SUM(quantity) AS total_quantity
                FROM orders
                GROUP BY product_id
            ) AS ordered
            WHERE p.id = ordered.product_id
            """
        )
    )

    # Delete orders only after their stock has been restored.
    connection.execute(
        sa.text("DELETE FROM orders")
    )


def downgrade() -> None:
    raise RuntimeError(
        "This data reset cannot reconstruct deleted orders. "
        "Restore a database backup if those records are needed."
    )
