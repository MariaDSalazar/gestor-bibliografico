"""Casos de uso del contexto Catálogo (documentos). Todo acotado por usuario."""

from __future__ import annotations

from ..domain.entities import Document
from ..domain.exceptions import NotFoundError, ValidationError
from ..domain.ports import DocumentRepository, MetadataExtractor


class DocumentService:
    def __init__(self, repo: DocumentRepository, extractor: MetadataExtractor):
        self._repo = repo
        self._extractor = extractor

    def list(self, user_id: int, collection: str | None = None) -> list[Document]:
        if collection == "none":
            return self._repo.list(user_id, uncategorized=True)
        if collection:
            return self._repo.list(user_id, collection_id=int(collection))
        return self._repo.list(user_id)

    def get(self, user_id: int, doc_id: int) -> Document:
        doc = self._repo.get(user_id, doc_id)
        if doc is None:
            raise NotFoundError("Documento no encontrado.")
        return doc

    def create(self, user_id: int, csl: dict) -> Document:
        if not csl or not isinstance(csl, dict):
            raise ValidationError("Falta el objeto CSL-JSON.")
        return self._repo.add(user_id, Document(csl=csl))

    def update(self, user_id: int, doc_id: int, csl: dict) -> Document:
        if not csl or not isinstance(csl, dict):
            raise ValidationError("Falta el objeto CSL-JSON.")
        doc = self._repo.update(user_id, doc_id, csl)
        if doc is None:
            raise NotFoundError("Documento no encontrado.")
        return doc

    def delete(self, user_id: int, doc_id: int) -> None:
        if not self._repo.remove(user_id, doc_id):
            raise NotFoundError("Documento no encontrado.")

    # --- PDF guardado en la BD ---
    def set_pdf(self, user_id: int, doc_id: int, data: bytes) -> None:
        if not data:
            raise ValidationError("El PDF está vacío.")
        if not self._repo.set_pdf(user_id, doc_id, data):
            raise NotFoundError("Documento no encontrado.")

    def get_pdf(self, user_id: int, doc_id: int) -> bytes:
        data = self._repo.get_pdf(user_id, doc_id)
        if data is None:
            raise NotFoundError("Este documento no tiene PDF adjunto.")
        return data

    # --- Importación (extracción de metadatos) ---
    async def import_from_input(self, text: str) -> tuple[dict, bytes | None]:
        """Devuelve (csl, pdf): el PDF solo si el enlace apuntaba a un PDF."""
        return await self._extractor.from_input(text)

    async def import_from_pdf(self, data: bytes) -> dict:
        return await self._extractor.from_pdf(data)
