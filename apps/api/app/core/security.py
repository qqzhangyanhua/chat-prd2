import os
import secrets
import warnings
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_explicit_key = settings.auth_secret_key or os.getenv("AUTH_SECRET_KEY")
if not _explicit_key:
    warnings.warn(
        "AUTH_SECRET_KEY not set; using random key — tokens will not survive restarts",
        stacklevel=1,
    )
SECRET_KEY = _explicit_key or secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.now(UTC) + expire_delta
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
