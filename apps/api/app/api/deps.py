from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.api_error import raise_api_error
from app.db.models import User
from app.db.session import SessionLocal
from app.services import auth as auth_service


http_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise_api_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="Not authenticated",
            recovery_action={
                "type": "login",
                "label": "重新登录",
                "target": "/login",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth_service.get_current_user_from_token(db, credentials.credentials)
