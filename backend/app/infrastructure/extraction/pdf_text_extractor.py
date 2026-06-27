"""Extracción de texto de PDF con pypdf (puro Python)."""

from __future__ import annotations

from io import BytesIO

from ...domain.exceptions import ExtractionError


def extract_text(data: bytes, max_pages: int = 3) -> str:
    """Texto de las primeras páginas (ahí suele estar el DOI)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
        parts = [page.extract_text() or "" for page in reader.pages[:max_pages]]
        return "\n".join(parts)
    except Exception as err:  # noqa: BLE001
        raise ExtractionError(f"No se pudo leer el PDF (¿escaneado o protegido?): {err}")
