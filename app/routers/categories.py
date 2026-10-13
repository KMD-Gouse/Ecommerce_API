from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Category
from app.schemas.categories import CreateCategory, CategoryResponse


router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)


# CREATE — admin only
@router.post(
    "",
    response_model=CategoryResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_category(
    category_data: CreateCategory,
    db: Annotated[Session, Depends(get_db)],
):
    category = Category(
        name=category_data.name,
    )

    db.add(category)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Category already exists",
        ) from None

    db.refresh(category)

    return category


# READ ALL — public
@router.get(
    "",
    response_model=list[CategoryResponse],
)
def get_categories(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    statement = (
        select(Category)
        .order_by(Category.id)
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()


# READ ONE — public
@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
)
def get_category(
    category_id: Annotated[int, Path(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    category = db.get(Category, category_id)

    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Category not found",
        )

    return category