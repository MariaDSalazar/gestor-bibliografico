"""Implementación SQLAlchemy del puerto UserRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..domain.entities import User
from .models import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session_factory: sessionmaker):
        self._sm = session_factory

    def get_by_username(self, username: str) -> User | None:
        with self._sm() as s:
            m = s.scalar(select(UserModel).where(UserModel.username == username))
            return self._to_entity(m) if m else None

    def get(self, user_id: int) -> User | None:
        with self._sm() as s:
            m = s.get(UserModel, user_id)
            return self._to_entity(m) if m else None

    def add(self, username: str, password_hash: str) -> User:
        with self._sm() as s:
            m = UserModel(username=username, password_hash=password_hash)
            s.add(m)
            s.commit()
            s.refresh(m)
            return self._to_entity(m)

    @staticmethod
    def _to_entity(m: UserModel) -> User:
        return User(id=m.id, username=m.username, password_hash=m.password_hash)
