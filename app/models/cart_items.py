from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0 AND quantity <= 1000",
            name="ck_cart_items_quantity_range",
        ),
        UniqueConstraint(
            "cart_id",
            "product_id",
            name="uq_cart_items_cart_product",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(nullable=False)

    cart = relationship(
        "Cart",
        back_populates="items",
    )

    product = relationship(
        "Product",
        back_populates="cart_items",
    )