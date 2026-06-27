"""Router de colecciones (carpetas) + pertenencia de documentos, por usuario."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....application.collections_service import CollectionService
from ..deps import collections_service, current_user_id
from ..schemas import CollectionIn, MemberIn, RenameIn, collection_to_api

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.get("")
def list_collections(uid: int = Depends(current_user_id), svc: CollectionService = Depends(collections_service)):
    return [collection_to_api(c) for c in svc.list(uid)]


@router.post("", status_code=201)
def create_collection(body: CollectionIn, uid: int = Depends(current_user_id), svc: CollectionService = Depends(collections_service)):
    return collection_to_api(svc.create(uid, body.name, body.parentId))


@router.patch("/{cid}")
def rename_collection(cid: int, body: RenameIn, uid: int = Depends(current_user_id), svc: CollectionService = Depends(collections_service)):
    return collection_to_api(svc.rename(uid, cid, body.name))


@router.delete("/{cid}", status_code=204)
def delete_collection(cid: int, uid: int = Depends(current_user_id), svc: CollectionService = Depends(collections_service)):
    svc.delete(uid, cid)


@router.post("/{cid}/documents", status_code=204)
def add_document(cid: int, body: MemberIn, uid: int = Depends(current_user_id), svc: CollectionService = Depends(collections_service)):
    svc.add_document(uid, cid, body.documentId)


@router.delete("/{cid}/documents/{doc_id}", status_code=204)
def remove_document(cid: int, doc_id: int, uid: int = Depends(current_user_id), svc: CollectionService = Depends(collections_service)):
    svc.remove_document(uid, cid, doc_id)
