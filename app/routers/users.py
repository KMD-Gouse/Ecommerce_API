from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, User
from app.schemas.users import CreateUser, UpdateUser, UserResponse
from app.security import hash_password


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# READ ALL
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


# CREATE
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        ) from None

    db.refresh(new_user)

    return {
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
    }


# UPDATE
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: Annotated[int, Path(gt=0)],
    user_update: UpdateUser,
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(User).where(User.id == user_id)
    user = db.scalars(statement).one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    changes = user_update.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    if "name" in changes:
        user.name = changes["name"]

    if "email" in changes:
        user.email = str(changes["email"])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        ) from None

    db.refresh(user)

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }


# READ ONE
@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(User).where(User.id == user_id)
    user = db.scalars(statement).one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }


# DELETE
@router.delete("/{user_id}")
def delete_user(
    user_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(User).where(User.id == user_id)
    user = db.scalars(statement).one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    existing_order_id = db.scalar(
        select(Order.id)
        .where(Order.user_id == user_id)
        .limit(1)
    )

    if existing_order_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a user with existing orders",
        )

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted successfully",
        "user_id": user_id,
    }