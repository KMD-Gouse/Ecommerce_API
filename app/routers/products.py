from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Order, Product
from app.schemas.products import (
    CreateProduct,
    ResponseProduct,
    UpdateProduct,
)


router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


# CREATE — admin only
@router.post(
    "",
    response_model=ResponseProduct,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_product(
    product: CreateProduct,
    db: Annotated[Session, Depends(get_db)],
):
    new_product = Product(
        name=product.name,
        price=product.price,
        stock=product.stock,
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "id": new_product.id,
        "name": new_product.name,
        "price": new_product.price,
        "stock": new_product.stock,
    }


# READ ALL — public
@router.get("", response_model=list[ResponseProduct])
def get_products(
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).order_by(Product.id)
    products = db.scalars(statement).all()

    return [
        {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "stock": product.stock,
        }
        for product in products
    ]


# READ ONE — public
@router.get("/{product_id}", response_model=ResponseProduct)
def get_product(
    product_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).where(
        Product.id == product_id
    )
    product = db.scalars(statement).one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
    }


# UPDATE — admin only
@router.patch(
    "/{product_id}",
    response_model=ResponseProduct,
    dependencies=[Depends(require_admin)],
)
def update_product(
    product_id: Annotated[int, Path(gt=0)],
    product_update: UpdateProduct,
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).where(
        Product.id == product_id
    )
    product = db.scalars(statement).one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    changes = product_update.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    if "name" in changes:
        product.name = changes["name"]

    if "price" in changes:
        product.price = changes["price"]

    if "stock" in changes:
        product.stock = changes["stock"]

    db.commit()
    db.refresh(product)

    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
    }


# DELETE — admin only
@router.delete(
    "/{product_id}",
    dependencies=[Depends(require_admin)],
)
def delete_product(
    product_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).where(
        Product.id == product_id
    )
    product = db.scalars(statement).one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    existing_order_id = db.scalar(
        select(Order.id)
        .where(Order.product_id == product_id)
        .limit(1)
    )

    if existing_order_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a product with existing orders",
        )

    db.delete(product)
    db.commit()

    return {
        "message": "Product deleted successfully",
        "product_id": product_id,
    }