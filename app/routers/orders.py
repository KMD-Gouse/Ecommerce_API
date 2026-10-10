from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product, User
from app.schemas.orders import (
    CreateOrder,
    OrderResponse,
    OrderResult,
    UpdateOrder,
)


router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


# Convert a database object into a response schema.
def to_order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        product_id=order.product_id,
        quantity=order.quantity,
    )


# CREATE
@router.post(
    "",
    response_model=OrderResult,
    status_code=201,
)
def create_order(
    order_data: CreateOrder,
    db: Annotated[Session, Depends(get_db)],
):
    with db.begin():
        # Check whether the user exists.
        statement = select(User).where(
            User.id == order_data.user_id
        )
        user = db.scalars(statement).one_or_none()

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        # Check whether the product exists.
        statement = select(Product).where(
            Product.id == order_data.product_id
        )
        product = db.scalars(statement).one_or_none()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        # Check available stock.
        if product.stock < order_data.quantity:
            raise HTTPException(
                status_code=409,
                detail="Not enough stock",
            )

        new_order = Order(
            user_id=user.id,
            product_id=product.id,
            quantity=order_data.quantity,
        )

        db.add(new_order)
        product.stock -= order_data.quantity

        # Write pending changes without committing.
        # This also gives new_order its generated ID.
        db.flush()

        result = to_order_response(new_order)

    # Successful exit from db.begin() commits the transaction.
    return {
        "message": "Order created successfully",
        "order": result,
    }


# READ ALL
@router.get("", response_model=list[OrderResponse])
def get_orders(
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Order).order_by(Order.id)
    orders = db.scalars(statement).all()

    return [
        to_order_response(order)
        for order in orders
    ]


# READ ONE
@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Order).where(
        Order.id == order_id
    )
    order = db.scalars(statement).one_or_none()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return to_order_response(order)


# UPDATE QUANTITY
@router.patch("/{order_id}", response_model=OrderResult)
def update_order(
    order_id: Annotated[int, Path(gt=0)],
    order_update: UpdateOrder,
    db: Annotated[Session, Depends(get_db)],
):
    with db.begin():
        # Find the existing order.
        statement = select(Order).where(
            Order.id == order_id
        )
        order = db.scalars(statement).one_or_none()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # Find the product associated with the order.
        statement = select(Product).where(
            Product.id == order.product_id
        )
        product = db.scalars(statement).one_or_none()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Order's product not found",
            )

        difference = order_update.quantity - order.quantity

        if difference > product.stock:
            raise HTTPException(
                status_code=409,
                detail="Not enough stock",
            )

        product.stock -= difference
        order.quantity = order_update.quantity

        result = to_order_response(order)

    return {
        "message": "Order updated successfully",
        "order": result,
    }


# DELETE / CANCEL
@router.delete("/{order_id}", response_model=OrderResult)
def delete_order(
    order_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    with db.begin():
        # Find the order.
        statement = select(Order).where(
            Order.id == order_id
        )
        order = db.scalars(statement).one_or_none()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # Find its product so stock can be restored.
        statement = select(Product).where(
            Product.id == order.product_id
        )
        product = db.scalars(statement).one_or_none()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Order's product not found",
            )

        product.stock += order.quantity

        db.delete(order)

    return {
        "message": "Order cancelled and stock restored",
    }