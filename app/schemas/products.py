from decimal import Decimal

from pydantic import BaseModel, Field


class CreateProduct(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100,
    )

    price: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    stock: int = Field(ge=0)

    category_id: int | None = Field(
        default=None,
        gt=0,
    )


class UpdateProduct(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    stock: int | None = Field(
        default=None,
        ge=0,
    )

    category_id: int | None = Field(
        default=None,
        gt=0,
    )


class ResponseProduct(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: int
    category_id: int | None
     


