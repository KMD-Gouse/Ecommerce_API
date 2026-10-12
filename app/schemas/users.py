from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict


class CreateUser(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)


class UpdateUser(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=50,
    )
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

class UserProfileResponse(UserResponse):
    role: Literal["customer", "admin"]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)