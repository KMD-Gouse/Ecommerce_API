from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Cart, CartItem, Product, User
from app.schemas.cart import (
    AddCartItem,
    CartItemResponse,
    CartResponse,
    UpdateCartItem,
)


router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
)


def find_my_cart(
    db: Session,
    user_id: int,
    *,
    lock: bool = False,
) -> Cart | None:
    statement = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
        )
    )

    if lock:
        statement = statement.with_for_update()

    return db.scalars(statement).one_or_none()


def to_cart_response(cart: Cart | None) -> CartResponse:
    if cart is None:
        return CartResponse(
            id=None,
            items=[],
            total_amount=Decimal("0.00"),
        )

    items = [
        CartItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name,
            quantity=item.quantity,
            unit_price=item.product.price,
            line_total=item.product.price * item.quantity,
        )
        for item in cart.items
    ]

    total = sum(
        (item.line_total for item in items),
        Decimal("0.00"),
    )

    return CartResponse(
        id=cart.id,
        items=items,
        total_amount=total,
    )


@router.get("", response_model=CartResponse)
def get_cart(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    cart = find_my_cart(db, current_user.id)

    return to_cart_response(cart)


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=201,
)
def add_item(
    item_data: AddCartItem,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        cart = find_my_cart(
            db,
            current_user.id,
            lock=True,
        )

        if cart is None:
            cart = Cart(user_id=current_user.id)
            db.add(cart)
            db.flush()

        product = db.get(Product, item_data.product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        existing_item = next(
            (
                item
                for item in cart.items
                if item.product_id == product.id
            ),
            None,
        )

        current_quantity = (
            existing_item.quantity
            if existing_item is not None
            else 0
        )

        new_quantity = current_quantity + item_data.quantity

        if new_quantity > 1000:
            raise HTTPException(
                status_code=422,
                detail="Cart item quantity cannot exceed 1000",
            )

        if new_quantity > product.stock:
            raise HTTPException(
                status_code=409,
                detail="Requested quantity exceeds current stock",
            )

        if existing_item is None:
            cart.items.append(
                CartItem(
                    product=product,
                    quantity=new_quantity,
                )
            )
        else:
            existing_item.quantity = new_quantity

        db.flush()
        result = to_cart_response(cart)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        # For example, two first-time requests tried to create
        # the same user's cart simultaneously.
        raise HTTPException(
            status_code=409,
            detail="Cart changed concurrently; retry",
        ) from exc

    except Exception:
        db.rollback()
        raise

    return result


@router.patch(
    "/items/{product_id}",
    response_model=CartResponse,
)
def set_item_quantity(
    product_id: Annotated[int, Path(gt=0)],
    item_data: UpdateCartItem,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        cart = find_my_cart(
            db,
            current_user.id,
            lock=True,
        )

        if cart is None:
            raise HTTPException(
                status_code=404,
                detail="Cart item not found",
            )

        item = next(
            (
                item
                for item in cart.items
                if item.product_id == product_id
            ),
            None,
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Cart item not found",
            )

        if item_data.quantity > item.product.stock:
            raise HTTPException(
                status_code=409,
                detail="Requested quantity exceeds current stock",
            )

        item.quantity = item_data.quantity

        db.flush()
        result = to_cart_response(cart)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return result


@router.delete(
    "/items/{product_id}",
    response_model=CartResponse,
)
def remove_item(
    product_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        cart = find_my_cart(
            db,
            current_user.id,
            lock=True,
        )

        if cart is None:
            raise HTTPException(
                status_code=404,
                detail="Cart item not found",
            )

        item = next(
            (
                item
                for item in cart.items
                if item.product_id == product_id
            ),
            None,
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Cart item not found",
            )

        cart.items.remove(item)

        db.flush()
        result = to_cart_response(cart)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return result