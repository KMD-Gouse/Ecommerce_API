from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateOrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CreateOrderItem] = Field(
        min_length=1,
        max_length=100,
    )


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: Literal["placed", "cancelled"]
    total_amount: Decimal
    created_at: datetime
    cancelled_at: datetime | None
    items: list[OrderItemResponse]


class OrderResult(BaseModel):
    message: str
    order: OrderResponse