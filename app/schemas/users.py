from pydantic import BaseModel, EmailStr, Field


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