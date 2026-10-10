
from typing import Annotated

from fastapi import APIRouter, Depends, Path
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
@router.post("", response_model=OrderResult)
def create_order(
    order_data: CreateOrder,
    db: Annotated[Session, Depends(get_db)],
):
    with db.begin():
        # Check the user.
        statement = select(User).where(
            User.id == order_data.user_id
        )
        user = db.scalars(statement).one_or_none()

        if user is None:
            return {"message": "User not found"}

        # Check the product.
        statement = select(Product).where(
            Product.id == order_data.product_id
        )
        product = db.scalars(statement).one_or_none()

        if product is None:
            return {"message": "Product not found"}

        # Check stock before changing anything.
        if product.stock < order_data.quantity:
            return {"message": "Not enough stock"}

        new_order = Order(
            user_id=user.id,
            product_id=product.id,
            quantity=order_data.quantity,
        )

        db.add(new_order)
        product.stock = product.stock - order_data.quantity

        # Send changes to the database, without committing yet.
        db.flush()

        result = to_order_response(new_order)

    # The transaction has committed before this return.
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

    response = []

    for order in orders:
        response.append(to_order_response(order))

    return response


# READ ONE
@router.get("/{order_id}", response_model=OrderResponse | None)
def get_order(
    order_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Order).where(Order.id == order_id)
    order = db.scalars(statement).one_or_none()

    if order is None:
        return None

    return to_order_response(order)


# UPDATE QUANTITY
@router.patch("/{order_id}", response_model=OrderResult)
def update_order(
    order_id: Annotated[int, Path(gt=0)],
    order_update: UpdateOrder,
    db: Annotated[Session, Depends(get_db)],
):
    with db.begin():
        statement = select(Order).where(Order.id == order_id)
        order = db.scalars(statement).one_or_none()

        if order is None:
            return {"message": "Order not found"}

        statement = select(Product).where(
            Product.id == order.product_id
        )
        product = db.scalars(statement).one_or_none()

        if product is None:
            return {"message": "Order's product not found"}

        difference = order_update.quantity - order.quantity

        if difference > product.stock:
            return {"message": "Not enough stock"}

        product.stock = product.stock - difference
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
        statement = select(Order).where(Order.id == order_id)
        order = db.scalars(statement).one_or_none()

        if order is None:
            return {"message": "Order not found"}

        statement = select(Product).where(
            Product.id == order.product_id
        )
        product = db.scalars(statement).one_or_none()

        if product is None:
            return {"message": "Order's product not found"}

        product.stock = product.stock + order.quantity

        db.delete(order)

    return {
        "message": "Order cancelled and stock restored",
    }