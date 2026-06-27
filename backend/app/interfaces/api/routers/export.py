"""Router de exportación: descarga de la lista de referencias ordenada A-Z.

Toma los documentos elegidos (o todos), los ordena alfabéticamente por el apellido
del primer autor (o el título si no hay autor) y genera el archivo en el formato pedido.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ....application.citations_service import CitationService
from ....application.documents_service import DocumentService
from ....domain.entities import Document
from ..deps import citations_service, current_user_id, documents_service
from ..schemas import ExportIn

router = APIRouter(prefix="/api/export", tags=["export"])


def _clave_alfabetica(doc: Document) -> str:
    autores = doc.authors
    if autores:
        a = autores[0]
        return (a.family or a.given or "").strip().lower()
    return (doc.title or "").strip().lower()


@router.post("")
def export(
    body: ExportIn,
    uid: int = Depends(current_user_id),
    docs: DocumentService = Depends(documents_service),
    cits: CitationService = Depends(citations_service),
):
    documentos = docs.list(uid) if not body.ids else [docs.get(uid, i) for i in body.ids]
    documentos.sort(key=_clave_alfabetica)

    contenido = cits.reference([d.csl for d in documentos], body.style)

    style = (body.style or "apa").lower()
    if style == "bibtex":
        nombre, media = "referencias.bib", "application/x-bibtex; charset=utf-8"
    else:
        nombre, media = f"referencias-{style}.txt", "text/plain; charset=utf-8"

    return Response(
        content=contenido,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
