"""Seguridad: hash de contraseñas (bcrypt) y tokens de sesión (JWT)."""

from __future__ import annotations

import os
import time

import bcrypt
import jwt

_SECRET = os.environ.get("BIBLIO_SECRET", "dev-secret-cambia-esto-en-produccion")
_ALG = "HS256"
_TTL = 60 * 60 * 24 * 30  # 30 días


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + _TTL}
    return jwt.encode(payload, _SECRET, algorithm=_ALG)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALG])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
