"""Router de documentos: importación automática (DOI/enlace/PDF) + CRUD, por usuario."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, Request, Response

from ....application.documents_service import DocumentService
from ..deps import current_user_id, documents_service
from ..schemas import DocIn, ImportIn, document_to_api

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(
    collection: str | None = None,
    uid: int = Depends(current_user_id),
    svc: DocumentService = Depends(documents_service),
):
    return [document_to_api(d) for d in svc.list(uid, collection)]


@router.get("/{doc_id}")
def get_document(doc_id: int, uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    return document_to_api(svc.get(uid, doc_id))


@router.post("/import")
async def import_link(body: ImportIn, _uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    """Extrae metadatos de un DOI/enlace. Si el enlace es un PDF, lo devuelve en base64."""
    csl, pdf = await svc.import_from_input(body.input)
    return {"csl": csl, "pdf": base64.b64encode(pdf).decode("ascii") if pdf else None}


@router.post("/import-pdf")
async def import_pdf(request: Request, _uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    """PDF en crudo (Content-Type: application/pdf). Devuelve CSL-JSON SIN guardar."""
    data = await request.body()
    return {"csl": await svc.import_from_pdf(data)}


@router.post("", status_code=201)
def create_document(body: DocIn, uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    return document_to_api(svc.create(uid, body.csl))


@router.put("/{doc_id}")
def update_document(doc_id: int, body: DocIn, uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    return document_to_api(svc.update(uid, doc_id, body.csl))


@router.post("/{doc_id}/pdf", status_code=204)
async def upload_pdf(doc_id: int, request: Request, uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    """Guarda el PDF (crudo, application/pdf) del documento en la base de datos."""
    svc.set_pdf(uid, doc_id, await request.body())


@router.get("/{doc_id}/pdf")
def get_pdf(doc_id: int, uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    """Sirve el PDF guardado (inline) para el visor."""
    data = svc.get_pdf(uid, doc_id)
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": "inline"})


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, uid: int = Depends(current_user_id), svc: DocumentService = Depends(documents_service)):
    svc.delete(uid, doc_id)
