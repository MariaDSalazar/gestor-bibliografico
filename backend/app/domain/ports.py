"""Puertos del dominio: interfaces abstractas que la infraestructura implementa.

La capa de aplicación depende de estos puertos, nunca de implementaciones
concretas (inversión de dependencias). Toda la biblioteca está acotada por usuario.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import Collection, Document, User


class UserRepository(ABC):
    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def get(self, user_id: int) -> User | None: ...

    @abstractmethod
    def add(self, username: str, password_hash: str) -> User: ...


class DocumentRepository(ABC):
    @abstractmethod
    def list(self, user_id: int, collection_id: int | None = None, uncategorized: bool = False) -> list[Document]: ...

    @abstractmethod
    def get(self, user_id: int, doc_id: int) -> Document | None: ...

    @abstractmethod
    def add(self, user_id: int, document: Document) -> Document: ...

    @abstractmethod
    def update(self, user_id: int, doc_id: int, csl: dict) -> Document | None: ...

    @abstractmethod
    def remove(self, user_id: int, doc_id: int) -> bool: ...

    # PDF guardado en la BD (no en disco)
    @abstractmethod
    def set_pdf(self, user_id: int, doc_id: int, data: bytes | None) -> bool: ...

    @abstractmethod
    def get_pdf(self, user_id: int, doc_id: int) -> bytes | None: ...


class CollectionRepository(ABC):
    @abstractmethod
    def list(self, user_id: int) -> list[Collection]: ...

    @abstractmethod
    def get(self, user_id: int, collection_id: int) -> Collection | None: ...

    @abstractmethod
    def add(self, user_id: int, name: str, parent_id: int | None = None) -> Collection: ...

    @abstractmethod
    def rename(self, user_id: int, collection_id: int, name: str) -> Collection | None: ...

    @abstractmethod
    def remove(self, user_id: int, collection_id: int) -> bool: ...

    @abstractmethod
    def add_document(self, user_id: int, collection_id: int, document_id: int) -> None: ...

    @abstractmethod
    def remove_document(self, user_id: int, collection_id: int, document_id: int) -> bool: ...


class MetadataExtractor(ABC):
    """Extrae CSL-JSON desde un DOI/enlace o desde un PDF."""

    @abstractmethod
    async def from_input(self, text: str) -> tuple[dict, bytes | None]:
        """Devuelve (csl, pdf). El PDF solo viene si el enlace apunta a un PDF."""

    @abstractmethod
    async def from_pdf(self, data: bytes) -> dict: ...


class CitationFormatter(ABC):
    """Genera referencias e in-text a partir de CSL-JSON."""

    @abstractmethod
    def reference(self, csl, style: str) -> str: ...

    @abstractmethod
    def in_text(self, csl: dict, opts: dict) -> str: ...
