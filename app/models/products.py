
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "price > 0",
            name="ck_products_price_positive",
        ),
        CheckConstraint(
            "stock >= 0",
            name="ck_products_stock_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    stock: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "categories.id",
            name="fk_products_category_id_categories",
        ),
        nullable=True,
        index=True,
    )

    category = relationship(
        "Category",
        back_populates="products",
    )

    orders = relationship(
        "Order",
        back_populates="product",
    )
    order_items = relationship(
        "OrderItem",
        back_populates="product",
    )