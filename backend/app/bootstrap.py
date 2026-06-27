"""Composition root: construye las implementaciones de infraestructura y las
inyecta en los servicios de aplicación. Es el único punto que conoce TODAS las capas.
"""

from __future__ import annotations

from pathlib import Path

from .application.auth_service import AuthService
from .application.citations_service import CitationService
from .application.collections_service import CollectionService
from .application.documents_service import DocumentService
from .infrastructure.citation.citeproc_formatter import CiteprocCitationFormatter
from .infrastructure.db import make_sessionmaker
from .infrastructure.extraction.http_metadata_extractor import HttpMetadataExtractor
from .infrastructure.sqlalchemy_collection_repository import SqlAlchemyCollectionRepository
from .infrastructure.sqlalchemy_document_repository import SqlAlchemyDocumentRepository
from .infrastructure.sqlalchemy_user_repository import SqlAlchemyUserRepository
from .interfaces.api.deps import Container


def build_container() -> Container:
    session_factory = make_sessionmaker()  # SQLite local o PostgreSQL (DATABASE_URL)

    document_repo = SqlAlchemyDocumentRepository(session_factory)
    collection_repo = SqlAlchemyCollectionRepository(session_factory)
    user_repo = SqlAlchemyUserRepository(session_factory)
    extractor = HttpMetadataExtractor()
    csl_dir = Path(__file__).resolve().parents[2] / "resources" / "csl"
    formatter = CiteprocCitationFormatter(csl_dir)

    return Container(
        documents=DocumentService(document_repo, extractor),
        collections=CollectionService(collection_repo),
        citations=CitationService(formatter),
        auth=AuthService(user_repo),
    )
