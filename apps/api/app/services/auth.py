from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token, hash_password
from app.db.models import User
from app.repositories import auth as auth_repository
from app.schemas.auth import RegisterRequest, UserResponse


def register(db: Session, payload: RegisterRequest) -> UserResponse:
    existing_user = auth_repository.get_user_by_email(db, payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = auth_repository.create_user(
        db=db,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    return UserResponse.model_validate(user)


def issue_token(user: UserResponse) -> str:
    return create_access_token(subject=user.id)


def get_current_user_from_token(db: Session, token: str) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_repository.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
