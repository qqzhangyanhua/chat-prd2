from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    statement = select(User).where(User.id == user_id)
    return db.execute(statement).scalar_one_or_none()


def create_user(db: Session, email: str, password_hash: str) -> User:
    user = User(id=str(uuid4()), email=email, password_hash=password_hash)
    db.add(user)
    db.flush()
    return user
