from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AddCartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class UpdateCartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(gt=0, le=1000)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class CartResponse(BaseModel):
    id: int | None
    items: list[CartItemResponse]
    total_amount: Decimal