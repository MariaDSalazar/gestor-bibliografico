"""Casos de uso del contexto Organización (carpetas). Todo acotado por usuario."""

from __future__ import annotations

from ..domain.entities import Collection
from ..domain.exceptions import NotFoundError, ValidationError
from ..domain.ports import CollectionRepository


class CollectionService:
    def __init__(self, repo: CollectionRepository):
        self._repo = repo

    def list(self, user_id: int) -> list[Collection]:
        return self._repo.list(user_id)

    def create(self, user_id: int, name: str, parent_id: int | None = None) -> Collection:
        name = (name or "").strip()
        if not name:
            raise ValidationError("El nombre de la carpeta es obligatorio.")
        return self._repo.add(user_id, name, parent_id)

    def rename(self, user_id: int, collection_id: int, name: str) -> Collection:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Nombre vacío.")
        updated = self._repo.rename(user_id, collection_id, name)
        if updated is None:
            raise NotFoundError("Carpeta no encontrada.")
        return updated

    def delete(self, user_id: int, collection_id: int) -> None:
        if not self._repo.remove(user_id, collection_id):
            raise NotFoundError("Carpeta no encontrada.")

    def add_document(self, user_id: int, collection_id: int, document_id: int) -> None:
        if not document_id:
            raise ValidationError("Falta documentId.")
        self._repo.add_document(user_id, collection_id, document_id)

    def remove_document(self, user_id: int, collection_id: int, document_id: int) -> None:
        if not self._repo.remove_document(user_id, collection_id, document_id):
            raise NotFoundError("El documento no estaba en esa carpeta.")
