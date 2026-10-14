"""Convert orders to purchase summaries

Revision ID: 0f0788062437
Revises: 4ee3f8db82a8
Create Date: 2026-10-14 12:04:27.422521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f0788062437'
down_revision: Union[str, Sequence[str], None] = '4ee3f8db82a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text("SET LOCAL lock_timeout = '5s'")
    )

    connection.execute(
        sa.text(
            """
            LOCK TABLE orders, order_items
            IN ACCESS EXCLUSIVE MODE
            """
        )
    )

    order_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM orders")
    ).scalar_one()

    item_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM order_items")
    ).scalar_one()

    if order_count != 0 or item_count != 0:
        raise RuntimeError(
            "Expected empty orders and order_items after the "
            "practice-data reset. Stop and inspect the data."
        )

    # Find the old product foreign key's actual database name.
    inspector = sa.inspect(connection)

    product_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("orders")
            if foreign_key["constrained_columns"] == ["product_id"]
        ),
        None,
    )

    if product_foreign_key is None:
        raise RuntimeError(
            "The expected orders.product_id foreign key was not found."
        )

    op.drop_constraint(
        product_foreign_key["name"],
        "orders",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_orders_product_id",
        table_name="orders",
    )

    op.drop_constraint(
        "ck_orders_quantity_positive",
        "orders",
        type_="check",
    )

    op.drop_column("orders", "product_id")
    op.drop_column("orders", "quantity")

    op.add_column(
        "orders",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'placed'"),
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "total_amount",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_orders_status_valid",
        "orders",
        "status IN ('placed', 'cancelled')",
    )

    op.create_check_constraint(
        "ck_orders_total_amount_positive",
        "orders",
        "total_amount > 0",
    )

    op.create_check_constraint(
        "ck_orders_cancellation_consistent",
        "orders",
        """
        (status = 'placed' AND cancelled_at IS NULL)
        OR
        (status = 'cancelled' AND cancelled_at IS NOT NULL)
        """,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    raise RuntimeError(
        "Automatic downgrade is not supported for this redesign. "
        "Multi-product orders cannot be converted back to the old "
        "single-product structure without a separate data migration."
    )
    # ### end Alembic commands ###
