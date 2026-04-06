from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import is_admin_email
from app.core.config import settings
from app.db.models import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services import auth as auth_service


router = APIRouter(prefix="/api/auth", tags=["auth"])


def build_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        is_admin=is_admin_email(user.email, settings.admin_emails),
    )


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = auth_service.register(db, payload.email, payload.password)
    token = auth_service.issue_token(user)
    return AuthResponse(user=build_user_response(user), access_token=token)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = auth_service.login(db, payload.email, payload.password)
    token = auth_service.issue_token(user)
    return AuthResponse(user=build_user_response(user), access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return build_user_response(current_user)
