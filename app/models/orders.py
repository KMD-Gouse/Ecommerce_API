from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship 
from sqlalchemy import CheckConstraint, ForeignKey

from app.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
    CheckConstraint(
        "quantity > 0",
        name="ck_orders_quantity_positive",
    ),
)

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
         index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
         index=True,
    )

    quantity: Mapped[int] = mapped_column(
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="orders",
    )

    product = relationship(
        "Product",
        back_populates="orders",
    )
    items = relationship(
        "OrderItem",
        back_populates="order",
        order_by="OrderItem.id",
    )