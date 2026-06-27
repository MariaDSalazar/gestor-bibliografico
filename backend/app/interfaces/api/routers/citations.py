"""Router de citas: referencias e in-text (Fase 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....application.citations_service import CitationService
from ..deps import citations_service
from ..schemas import InTextIn, ReferenceIn

router = APIRouter(prefix="/api/citations", tags=["citations"])


@router.post("/reference")
def make_reference(body: ReferenceIn, svc: CitationService = Depends(citations_service)):
    return {"result": svc.reference(body.csl, body.style)}


@router.post("/in-text")
def make_in_text(body: InTextIn, svc: CitationService = Depends(citations_service)):
    opts = body.model_dump(exclude={"csl"})
    return {"result": svc.in_text(body.csl, opts)}
