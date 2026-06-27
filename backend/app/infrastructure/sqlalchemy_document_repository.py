"""Implementación SQLAlchemy del puerto DocumentRepository (acotado por usuario)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ..domain.entities import Document
from .models import DocumentModel, document_collections


class SqlAlchemyDocumentRepository:
    def __init__(self, session_factory: sessionmaker):
        self._sm = session_factory

    def list(self, user_id: int, collection_id: int | None = None, uncategorized: bool = False) -> list[Document]:
        with self._sm() as s:
            stmt = select(DocumentModel).where(DocumentModel.user_id == user_id)
            if collection_id:
                stmt = stmt.join(
                    document_collections, document_collections.c.document_id == DocumentModel.id
                ).where(document_collections.c.collection_id == collection_id)
            elif uncategorized:
                sub = select(document_collections.c.document_id)
                stmt = stmt.where(~DocumentModel.id.in_(sub))
            stmt = stmt.order_by(DocumentModel.date_added.desc(), DocumentModel.id.desc())
            return [self._to_entity(m) for m in s.scalars(stmt).all()]

    def get(self, user_id: int, doc_id: int) -> Document | None:
        with self._sm() as s:
            m = s.get(DocumentModel, doc_id)
            return self._to_entity(m) if (m and m.user_id == user_id) else None

    def add(self, user_id: int, document: Document) -> Document:
        with self._sm() as s:
            m = DocumentModel(user_id=user_id, **self._cols(document))
            s.add(m)
            s.commit()
            s.refresh(m)
            return self._to_entity(m)

    def update(self, user_id: int, doc_id: int, csl: dict) -> Document | None:
        with self._sm() as s:
            m = s.get(DocumentModel, doc_id)
            if not m or m.user_id != user_id:
                return None
            for k, v in self._cols(Document(csl=csl)).items():
                setattr(m, k, v)
            s.commit()
            s.refresh(m)
            return self._to_entity(m)

    def remove(self, user_id: int, doc_id: int) -> bool:
        with self._sm() as s:
            m = s.get(DocumentModel, doc_id)
            if not m or m.user_id != user_id:
                return False
            s.delete(m)
            s.commit()
            return True

    def set_pdf(self, user_id: int, doc_id: int, data: bytes | None) -> bool:
        with self._sm() as s:
            m = s.get(DocumentModel, doc_id)
            if not m or m.user_id != user_id:
                return False
            m.pdf = data
            s.commit()
            return True

    def get_pdf(self, user_id: int, doc_id: int) -> bytes | None:
        with self._sm() as s:
            m = s.get(DocumentModel, doc_id)
            if not m or m.user_id != user_id or m.pdf is None:
                return None
            return bytes(m.pdf)

    # --- mapeo ---
    @staticmethod
    def _to_entity(m: DocumentModel) -> Document:
        return Document(
            csl=m.csl_json or {},
            id=m.id,
            date_added=str(m.date_added) if m.date_added else None,
            has_pdf=m.pdf is not None,
        )

    @staticmethod
    def _cols(doc: Document) -> dict:
        return {
            "type": doc.type,
            "title": doc.title,
            "year": doc.year,
            "container_title": doc.container_title,
            "publisher": doc.publisher,
            "doi": doc.doi,
            "url": doc.url,
            "abstract": doc.abstract,
            "csl_json": doc.csl,
        }
