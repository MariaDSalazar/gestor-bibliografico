"""Router de autenticación: registro, login y usuario actual."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ....application.auth_service import AuthService
from ..deps import auth_service, current_user_id
from ..schemas import Credentials

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(body: Credentials, svc: AuthService = Depends(auth_service)):
    token = svc.register(body.username, body.password)
    return {"token": token, "username": body.username.strip()}


@router.post("/login")
def login(body: Credentials, svc: AuthService = Depends(auth_service)):
    token = svc.login(body.username, body.password)
    return {"token": token, "username": body.username.strip()}


@router.get("/me")
def me(uid: int = Depends(current_user_id), svc: AuthService = Depends(auth_service)):
    user = svc.user_for(uid)
    if user is None:
        raise HTTPException(status_code=401, detail="Sesión inválida.")
    return {"id": user.id, "username": user.username}
