"""Schemas de entrada/salida (pydantic) y presentadores de entidades de dominio."""

from __future__ import annotations

from pydantic import BaseModel

from ...domain.entities import Collection, Document


# --- Entrada ---
class Credentials(BaseModel):
    username: str = ""
    password: str = ""


class ImportIn(BaseModel):
    input: str = ""


class DocIn(BaseModel):
    csl: dict


class CollectionIn(BaseModel):
    name: str = ""
    parentId: int | None = None


class RenameIn(BaseModel):
    name: str = ""


class MemberIn(BaseModel):
    documentId: int


class ReferenceIn(BaseModel):
    csl: dict | list
    style: str = "apa"


class FuenteOriginal(BaseModel):
    autor: str = ""
    anio: str = ""


class ExportIn(BaseModel):
    ids: list[int] | None = None  # None o lista vacía = todos
    style: str = "apa"            # apa | ieee | bibtex


class InTextIn(BaseModel):
    csl: dict
    variante: str = "parenthetical"
    pagina: str | None = None
    textoCitado: str | None = None
    autorOriginal: str | None = None  # cita de fuente secundaria ("como se citó en")
    anioOriginal: str | None = None
    fuentes: list[FuenteOriginal] | None = None  # varias fuentes originales secundarias


# --- Presentadores (entidad → dict para la API) ---
def document_to_api(doc: Document) -> dict:
    return {
        "id": doc.id,
        "type": doc.type,
        "title": doc.title,
        "year": doc.year,
        "container_title": doc.container_title,
        "publisher": doc.publisher,
        "doi": doc.doi,
        "url": doc.url,
        "date_added": doc.date_added,
        "has_pdf": doc.has_pdf,
        "csl": doc.csl,
    }


def collection_to_api(col: Collection) -> dict:
    return {"id": col.id, "name": col.name, "parent_id": col.parent_id, "doc_count": col.doc_count}
