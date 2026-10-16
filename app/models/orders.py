from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        CheckConstraint(
            "status IN ('placed', 'cancelled')",
            name="ck_orders_status_valid",
        ),
        CheckConstraint(
            "total_amount > 0",
            name="ck_orders_total_amount_positive",
        ),
        CheckConstraint(
            """
            (status = 'placed' AND cancelled_at IS NULL)
            OR
            (status = 'cancelled' AND cancelled_at IS NOT NULL)
            """,
            name="ck_orders_cancellation_consistent",
        ),
                UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_orders_user_idempotency_key",
        ),
        CheckConstraint(
            """
            (idempotency_key IS NULL AND checkout_fingerprint IS NULL)
            OR
            (idempotency_key IS NOT NULL AND checkout_fingerprint IS NOT NULL)
            """,
            name="ck_orders_checkout_fields_together",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'placed'"),
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="orders",
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        order_by="OrderItem.id",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    checkout_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )