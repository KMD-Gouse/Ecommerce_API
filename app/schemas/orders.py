# app/schemas/order.py

from pydantic import BaseModel, Field


class CreateOrder(BaseModel):
    user_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class UpdateOrder(BaseModel):
    quantity: int = Field(gt=0)


class OrderResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int


class OrderResult(BaseModel):
    message: str
    order: OrderResponse | None = None    