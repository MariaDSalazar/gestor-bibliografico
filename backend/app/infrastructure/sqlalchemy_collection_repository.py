"""Implementación SQLAlchemy del puerto CollectionRepository (acotado por usuario)."""

from __future__ import annotations

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import sessionmaker

from ..domain.entities import Collection
from .models import CollectionModel, DocumentModel, document_collections


class SqlAlchemyCollectionRepository:
    def __init__(self, session_factory: sessionmaker):
        self._sm = session_factory

    def list(self, user_id: int) -> list[Collection]:
        with self._sm() as s:
            rows = s.execute(
                select(
                    CollectionModel.id,
                    CollectionModel.name,
                    CollectionModel.parent_id,
                    select(func.count())
                    .select_from(document_collections)
                    .where(document_collections.c.collection_id == CollectionModel.id)
                    .scalar_subquery()
                    .label("doc_count"),
                )
                .where(CollectionModel.user_id == user_id)
                .order_by(func.lower(CollectionModel.name))
            ).all()
            return [Collection(id=r.id, name=r.name, parent_id=r.parent_id, doc_count=r.doc_count) for r in rows]

    def get(self, user_id: int, collection_id: int) -> Collection | None:
        with self._sm() as s:
            m = s.get(CollectionModel, collection_id)
            if not m or m.user_id != user_id:
                return None
            return Collection(id=m.id, name=m.name, parent_id=m.parent_id, doc_count=0)

    def add(self, user_id: int, name: str, parent_id: int | None = None) -> Collection:
        with self._sm() as s:
            m = CollectionModel(user_id=user_id, name=name, parent_id=parent_id)
            s.add(m)
            s.commit()
            s.refresh(m)
            return Collection(id=m.id, name=m.name, parent_id=m.parent_id, doc_count=0)

    def rename(self, user_id: int, collection_id: int, name: str) -> Collection | None:
        with self._sm() as s:
            m = s.get(CollectionModel, collection_id)
            if not m or m.user_id != user_id:
                return None
            m.name = name
            s.commit()
            return Collection(id=m.id, name=m.name, parent_id=m.parent_id, doc_count=0)

    def remove(self, user_id: int, collection_id: int) -> bool:
        with self._sm() as s:
            m = s.get(CollectionModel, collection_id)
            if not m or m.user_id != user_id:
                return False
            s.delete(m)
            s.commit()
            return True

    def add_document(self, user_id: int, collection_id: int, document_id: int) -> None:
        with self._sm() as s:
            if not self._owns(s, user_id, collection_id, document_id):
                return
            exists = s.execute(
                select(document_collections).where(
                    document_collections.c.collection_id == collection_id,
                    document_collections.c.document_id == document_id,
                )
            ).first()
            if not exists:
                s.execute(insert(document_collections).values(collection_id=collection_id, document_id=document_id))
                s.commit()

    def remove_document(self, user_id: int, collection_id: int, document_id: int) -> bool:
        with self._sm() as s:
            if not self._owns(s, user_id, collection_id, document_id):
                return False
            res = s.execute(
                delete(document_collections).where(
                    document_collections.c.collection_id == collection_id,
                    document_collections.c.document_id == document_id,
                )
            )
            s.commit()
            return res.rowcount > 0

    @staticmethod
    def _owns(s, user_id: int, collection_id: int, document_id: int) -> bool:
        c = s.get(CollectionModel, collection_id)
        d = s.get(DocumentModel, document_id)
        return bool(c and d and c.user_id == user_id and d.user_id == user_id)
