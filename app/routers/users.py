from fastapi import APIRouter

from app.schemas.users import CreateUser, UpdateUser, UserResponse
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.users import CreateUser, UpdateUser, UserResponse
from app.security import hash_password


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

@router.get("", response_model=list[UserResponse])
def get_users(
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(User).order_by(User.id)

    users = db.scalars(statement).all()

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        }
        for user in users
    ]

@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    user: CreateUser,
    db: Annotated[Session, Depends(get_db)],
):
    new_user = User(
        name=user.name,
        email=str(user.email),
        hashed_password=hash_password(user.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
    }

@router.patch("/{user_id}", response_model=UserResponse | None)
def update_user(
    user_id: int,
    user_update: UpdateUser,
    db: Annotated[Session, Depends(get_db)],
):
    # Find the existing user.
    statement = select(User).where(User.id == user_id)
    user = db.scalars(statement).one_or_none()

    if user is None:
        return None

    # Keep only supplied fields with non-None values.
    changes = user_update.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    # Modify the database object.
    if "name" in changes:
        user.name = changes["name"]

    if "email" in changes:
        user.email = str(changes["email"])

    # Save and reload the updated record.
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }

@router.get("/{user_id}", response_model=UserResponse | None)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(User).where(User.id == user_id)

    user = db.scalars(statement).one_or_none()

    if user is None:
        return None

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(User).where(User.id == user_id)
    user = db.scalars(statement).one_or_none()

    if user is None:
        return {"message": "User not found"}

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted successfully",
        "user_id": user_id,
    }