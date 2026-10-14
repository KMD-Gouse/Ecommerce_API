from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Order, OrderItem, Product, User
from app.schemas.orders import (
    CreateOrder,
    OrderResponse,
    OrderResult,
)


router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


def find_order(
    db: Session,
    order_id: int,
    current_user: User,
    *,
    lock: bool = False,
) -> Order:
    statement = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    )

    if current_user.role != "admin":
        statement = statement.where(
            Order.user_id == current_user.id
        )

    if lock:
        statement = statement.with_for_update()

    order = db.scalars(statement).one_or_none()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return order


# CREATE — authenticated user
@router.post(
    "",
    response_model=OrderResult,
    status_code=201,
)
def create_order(
    order_data: CreateOrder,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        product_ids = [
            item.product_id
            for item in order_data.items
        ]

        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(
                status_code=422,
                detail="Each product must appear only once",
            )

        statement = (
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )

        products = db.scalars(statement).all()

        products_by_id = {
            product.id: product
            for product in products
        }

        # Validate every requested item before changing stock.
        for item_data in order_data.items:
            product = products_by_id.get(item_data.product_id)

            if product is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {item_data.product_id} not found",
                )

            if product.stock < item_data.quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Not enough stock for product {product.id}",
                )

        total_amount = sum(
            (
                products_by_id[item.product_id].price
                * item.quantity
                for item in order_data.items
            ),
            Decimal("0.00"),
        )

        order = Order(
            user_id=current_user.id,
            status="placed",
            total_amount=total_amount,
        )

        for item_data in order_data.items:
            product = products_by_id[item_data.product_id]

            order.items.append(
                OrderItem(
                    product_id=product.id,
                    quantity=item_data.quantity,
                    unit_price=product.price,
                )
            )

            product.stock -= item_data.quantity

        db.add(order)
        db.flush()

        result = OrderResponse.model_validate(order)

        db.commit()

    except Exception:
        db.rollback()
        raise

    return OrderResult(
        message="Order created successfully",
        order=result,
    )


# READ ALL — customers see their own; admins see all
@router.get(
    "",
    response_model=list[OrderResponse],
)
def get_orders(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    statement = (
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.id.desc())
        .offset(offset)
        .limit(limit)
    )

    if current_user.role != "admin":
        statement = statement.where(
            Order.user_id == current_user.id
        )

    return db.scalars(statement).all()


# READ ONE
@router.get(
    "/{order_id}",
    response_model=OrderResponse,
)
def get_order(
    order_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return find_order(
        db,
        order_id,
        current_user,
    )


# CANCEL — preserve the order and restore stock once
@router.post(
    "/{order_id}/cancel",
    response_model=OrderResult,
)
def cancel_order(
    order_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        order = find_order(
            db,
            order_id,
            current_user,
            lock=True,
        )

        if order.status == "placed":
            if not order.items:
                raise HTTPException(
                    status_code=409,
                    detail="Order has no items",
                )

            product_ids = [
                item.product_id
                for item in order.items
            ]

            statement = (
                select(Product)
                .where(Product.id.in_(product_ids))
                .order_by(Product.id)
                .with_for_update()
            )

            products = db.scalars(statement).all()

            products_by_id = {
                product.id: product
                for product in products
            }

            if len(products_by_id) != len(set(product_ids)):
                raise HTTPException(
                    status_code=409,
                    detail="An order product is missing",
                )

            for item in order.items:
                product = products_by_id[item.product_id]
                product.stock += item.quantity

            order.status = "cancelled"
            order.cancelled_at = datetime.now(timezone.utc)

        db.flush()

        result = OrderResponse.model_validate(order)

        db.commit()

    except Exception:
        db.rollback()
        raise

    return OrderResult(
        message="Order is cancelled",
        order=result,
    )