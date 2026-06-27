"""Inyección de dependencias: expone los servicios y el usuario autenticado a los routers."""

from __future__ import annotations

from fastapi import Header, HTTPException

from ...application.auth_service import AuthService
from ...application.citations_service import CitationService
from ...application.collections_service import CollectionService
from ...application.documents_service import DocumentService
from ...infrastructure.security import decode_token


class Container:
    def __init__(
        self,
        documents: DocumentService,
        collections: CollectionService,
        citations: CitationService,
        auth: AuthService,
    ):
        self.documents = documents
        self.collections = collections
        self.citations = citations
        self.auth = auth


_container: Container | None = None


def set_container(container: Container) -> None:
    global _container
    _container = container


def _get() -> Container:
    if _container is None:
        raise RuntimeError("Contenedor no inicializado (composition root).")
    return _container


def documents_service() -> DocumentService:
    return _get().documents


def collections_service() -> CollectionService:
    return _get().collections


def citations_service() -> CitationService:
    return _get().citations


def auth_service() -> AuthService:
    return _get().auth


def current_user_id(authorization: str = Header(default="")) -> int:
    """Extrae y valida el usuario del token Bearer. 401 si falta o es inválido."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado.")
    uid = decode_token(authorization[7:])
    if uid is None:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")
    return uid
