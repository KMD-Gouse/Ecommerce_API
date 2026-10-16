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
import hashlib
import json

from fastapi import Header

from app.models import Order, OrderItem
from app.schemas.orders import OrderResponse, OrderResult


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
def cart_fingerprint(items: list[CartItem]) -> str:
    """Give the cart contents a stable identifier, regardless of item order."""
    contents = sorted(
        (item.product_id, item.quantity)
        for item in items
    )

    encoded = json.dumps(
        contents,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


@router.post(
    "/checkout",
    response_model=OrderResult,
    status_code=201,
)
def checkout_cart(
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
        ),
    ],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    key = idempotency_key.strip()

    if not key:
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key cannot be blank",
        )

    try:
        # Cart operations in this project also lock this row.
        # A second checkout for this cart waits for the first to finish.
        cart = find_my_cart(
            db,
            current_user.id,
            lock=True,
        )

        # Check this AFTER acquiring the cart lock. A checkout that
        # was in progress may have committed while we waited.
        existing_order = db.scalar(
            select(Order)
            .where(
                Order.user_id == current_user.id,
                Order.idempotency_key == key,
            )
            .options(selectinload(Order.items))
        )

        if existing_order is not None:
            if (
                cart is not None
                and cart.items
                and cart_fingerprint(cart.items)
                != existing_order.checkout_fingerprint
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was used for a different cart",
                )

            result = OrderResponse.model_validate(existing_order)
            db.rollback()  # Release the cart lock; nothing was changed.

            return OrderResult(
                message="Order already created",
                order=result,
            )

        if cart is None or not cart.items:
            raise HTTPException(
                status_code=409,
                detail="Cart is empty",
            )

        if len(cart.items) > 100:
            raise HTTPException(
                status_code=422,
                detail="Cart cannot contain more than 100 products",
            )

        fingerprint = cart_fingerprint(cart.items)

        product_ids = [
            item.product_id
            for item in cart.items
        ]

        # Lock product rows in a consistent order before checking stock.
        statement = (
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        products = db.scalars(statement).all()
        products_by_id = {
            product.id: product
            for product in products
        }

        # Validate all items before changing any stock.
        for item in cart.items:
            product = products_by_id.get(item.product_id)

            if product is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Product {item.product_id} is unavailable",
                )

            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Not enough stock for product {product.id}",
                )

        total_amount = sum(
            (
                products_by_id[item.product_id].price * item.quantity
                for item in cart.items
            ),
            Decimal("0.00"),
        )

        order = Order(
            user_id=current_user.id,
            status="placed",
            total_amount=total_amount,
            idempotency_key=key,
            checkout_fingerprint=fingerprint,
        )

        for item in cart.items:
            product = products_by_id[item.product_id]

            order.items.append(
                OrderItem(
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )

            product.stock -= item.quantity

        db.add(order)

        # CartItem has delete-orphan configured in your model.
        cart.items.clear()

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