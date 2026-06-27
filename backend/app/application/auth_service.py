"""Caso de uso de autenticación: registro y login con usuario/contraseña."""

from __future__ import annotations

from ..domain.entities import User
from ..domain.exceptions import ValidationError
from ..domain.ports import UserRepository
from ..infrastructure.security import create_token, hash_password, verify_password


class AuthService:
    def __init__(self, users: UserRepository):
        self._users = users

    def register(self, username: str, password: str) -> str:
        username = (username or "").strip()
        if len(username) < 3:
            raise ValidationError("El usuario debe tener al menos 3 caracteres.")
        if len(password or "") < 6:
            raise ValidationError("La contraseña debe tener al menos 6 caracteres.")
        if self._users.get_by_username(username):
            raise ValidationError("Ese usuario ya existe.")
        user = self._users.add(username, hash_password(password))
        return create_token(user.id)

    def login(self, username: str, password: str) -> str:
        user = self._users.get_by_username((username or "").strip())
        if not user or not verify_password(password or "", user.password_hash or ""):
            raise ValidationError("Usuario o contraseña incorrectos.")
        return create_token(user.id)

    def user_for(self, user_id: int) -> User | None:
        return self._users.get(user_id)
