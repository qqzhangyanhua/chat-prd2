from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.api_error import raise_api_error
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.repositories import auth as auth_repository


def register(db: Session, email: str, password: str) -> User:
    existing_user = auth_repository.get_user_by_email(db, email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    try:
        user = auth_repository.create_user(
            db=db,
            email=email,
            password_hash=hash_password(password),
        )
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=user.id)


def login(db: Session, email: str, password: str) -> User:
    user = auth_repository.get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return user


def get_current_user_from_token(db: Session, token: str) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise_api_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID",
            message="Invalid authentication credentials",
            recovery_action={
                "type": "login",
                "label": "重新登录",
                "target": "/login",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise_api_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID",
            message="Invalid authentication credentials",
            recovery_action={
                "type": "login",
                "label": "重新登录",
                "target": "/login",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_repository.get_user_by_id(db, user_id)
    if user is None:
        raise_api_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID",
            message="Invalid authentication credentials",
            recovery_action={
                "type": "login",
                "label": "重新登录",
                "target": "/login",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
