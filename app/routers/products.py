
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas.products import (
    CreateProduct,
    ResponseProduct,
    UpdateProduct,
)


router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


# CREATE
@router.post("", response_model=ResponseProduct, status_code=201)
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


# READ ALL
@router.get("", response_model=list[ResponseProduct])
def get_products(
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).order_by(Product.id)
    products = db.scalars(statement).all()

    response = []

    for product in products:
        response.append({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "stock": product.stock,
        })

    return response


# READ ONE
@router.get("/{product_id}", response_model=ResponseProduct | None)
def get_product(
    product_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).where(Product.id == product_id)
    product = db.scalars(statement).one_or_none()

    if product is None:
        return None

    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
    }


# UPDATE
@router.patch("/{product_id}", response_model=ResponseProduct | None)
def update_product(
    product_id: Annotated[int, Path(gt=0)],
    product_update: UpdateProduct,
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).where(Product.id == product_id)
    product = db.scalars(statement).one_or_none()

    if product is None:
        return None

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


# DELETE
@router.delete("/{product_id}")
def delete_product(
    product_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(Product).where(Product.id == product_id)
    product = db.scalars(statement).one_or_none()

    if product is None:
        return {"message": "Product not found"}

    db.delete(product)
    db.commit()

    return {
        "message": "Product deleted successfully",
        "product_id": product_id,
    }
