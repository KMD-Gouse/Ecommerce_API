from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.auth import TokenResponse
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Used when the email does not exist, so we still perform
# a password-hash verification.
DUMMY_PASSWORD_HASH = hash_password(
    "dummy-password-not-used-by-an-account"
)


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    # The form field is named "username", but we use email.
    statement = select(User).where(
        User.email == form_data.username
    )

    user = db.scalars(statement).one_or_none()

    stored_hash = (
        user.hashed_password
        if user is not None
        else DUMMY_PASSWORD_HASH
    )

    password_matches = verify_password(
        form_data.password,
        stored_hash,
    )

    if user is None or not password_matches:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is inactive",
        )

    access_token = create_access_token(user.id)

    return TokenResponse(
        access_token=access_token,
    )