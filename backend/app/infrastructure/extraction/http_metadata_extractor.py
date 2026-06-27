"""Adaptador que implementa MetadataExtractor vía doi.org/Crossref (httpx) + PDF.

Estrategia (CONTEXTO.md §6):
  1) DOI / enlace con DOI → doi.org (content negotiation) → CSL-JSON.
  2) URL de publicación   → se busca el DOI en el HTML (<meta citation_doi>).
  3) PDF                  → se busca el DOI en el texto → doi.org.
  4) PDF sin DOI          → el usuario completa los datos a mano (visor de PDF en la app).
"""

from __future__ import annotations

import os
import re
from html import unescape

import httpx

from ...domain.exceptions import ExtractionError
from ...domain.ports import MetadataExtractor
from .pdf_text_extractor import extract_text

# "Polite pool": identificarse en las peticiones (buena práctica Crossref/doi.org).
CONTACT_EMAIL = os.environ.get("BIBLIO_EMAIL", "cojeda@bestlinesoft.com")
USER_AGENT = f"GestorBibliografico/0.1 (mailto:{CONTACT_EMAIL})"
CSL_ACCEPT = "application/vnd.citationstyles.csl+json"

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
ARXIV_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})|arXiv:\s*(\d{4}\.\d{4,5})", re.IGNORECASE)
CITATION_DOI_RE = re.compile(
    r'<meta[^>]+name=["\']citation_doi["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_doi["\']',
    re.IGNORECASE,
)


class HttpMetadataExtractor(MetadataExtractor):
    async def from_input(self, text: str) -> tuple[dict, bytes | None]:
        """Devuelve (csl, pdf). El PDF solo viene cuando el enlace apunta a un PDF."""
        s = (text or "").strip()
        if not s:
            raise ExtractionError("Introduce un DOI o un enlace.")

        arxiv = _match_arxiv(s)
        if arxiv:
            csl = await self._from_doi(f"10.48550/arXiv.{arxiv}")
            return csl, await self._download_pdf(f"https://arxiv.org/pdf/{arxiv}")

        doi = _parse_doi(s)
        if doi:
            csl = await self._from_doi(doi)
            return csl, await self._oa_pdf(doi)  # intenta el PDF open access

        if re.match(r"^https?://", s, re.IGNORECASE):
            return await self._from_url(s)

        raise ExtractionError("No reconozco eso como DOI ni como enlace válido.")

    async def _oa_pdf(self, doi: str) -> bytes | None:
        """Busca el PDF en acceso abierto del DOI vía Unpaywall (si existe)."""
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
                res = await client.get(
                    f"https://api.unpaywall.org/v2/{_clean_doi(doi)}",
                    params={"email": CONTACT_EMAIL},
                )
            if res.status_code != 200:
                return None
            loc = res.json().get("best_oa_location") or {}
            url = loc.get("url_for_pdf") or loc.get("url")
            return await self._download_pdf(url) if url else None
        except (httpx.HTTPError, ValueError, KeyError):
            return None

    async def _download_pdf(self, url: str) -> bytes | None:
        """Descarga un PDF si es accesible y razonable (<25 MB). Nunca lanza."""
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                res = await client.get(url, headers={"User-Agent": USER_AGENT})
            if res.status_code >= 400:
                return None
            data = res.content
            ctype = res.headers.get("content-type", "").lower()
            es_pdf = "application/pdf" in ctype or data[:5] == b"%PDF-"
            return data if (es_pdf and 0 < len(data) <= 25 * 1024 * 1024) else None
        except httpx.HTTPError:
            return None

    async def from_pdf(self, data: bytes) -> dict:
        if not data:
            raise ExtractionError("El PDF está vacío o no se pudo leer.")
        text = extract_text(data)
        doi = _parse_doi(text)
        if doi:
            return await self._from_doi(doi)
        arxiv = _match_arxiv(text)
        if arxiv:
            return await self._from_doi(f"10.48550/arXiv.{arxiv}")
        raise ExtractionError(
            "El PDF no contiene un DOI detectable. Revísalo en el visor y completa los datos a mano."
        )

    # --- internos ---
    async def _from_doi(self, doi: str) -> dict:
        clean = _clean_doi(doi)
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            res = await client.get(
                f"https://doi.org/{clean}",
                headers={"Accept": CSL_ACCEPT, "User-Agent": USER_AGENT},
            )
        if res.status_code == 404:
            raise ExtractionError(f"DOI no encontrado: {clean}")
        if res.status_code >= 400:
            raise ExtractionError(f"Error consultando el DOI ({res.status_code}).")
        return _normalize_csl(res.json())

    async def _from_url(self, url: str) -> tuple[dict, bytes | None]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            res = await client.get(url, headers={"User-Agent": USER_AGENT})
        if res.status_code >= 400:
            raise ExtractionError(f"No se pudo abrir el enlace ({res.status_code}).")

        ctype = res.headers.get("content-type", "").lower()
        es_pdf = "application/pdf" in ctype or url.lower().split("?")[0].endswith(".pdf")
        if es_pdf:
            # Enlace directo a un PDF: lo descargamos, extraemos su texto y buscamos el DOI.
            data = res.content
            if len(data) > 25 * 1024 * 1024:  # límite 25 MB
                raise ExtractionError("El PDF del enlace es demasiado grande (más de 25 MB).")
            text = extract_text(data)
            doi = _parse_doi(text)
            if doi:
                return await self._from_doi(doi), data
            arxiv = _match_arxiv(text)
            if arxiv:
                return await self._from_doi(f"10.48550/arXiv.{arxiv}"), data
            return {"type": "article-journal"}, data  # CSL mínimo; se completa a mano viendo el PDF

        # Página HTML: si hay DOI, lo resolvemos; si no, generamos una referencia de página web.
        html = res.text
        m = CITATION_DOI_RE.search(html)
        doi = (m.group(1) or m.group(2)) if m else _parse_doi(html)
        if doi:
            return await self._from_doi(doi), None
        return _webpage_csl(html, str(res.url)), None


def _parse_doi(s: str) -> str | None:
    m = DOI_RE.search(s or "")
    return _clean_doi(m.group(0)) if m else None


def _match_arxiv(s: str) -> str | None:
    m = ARXIV_RE.search(s or "")
    return (m.group(1) or m.group(2)) if m else None


def _clean_doi(doi: str) -> str:
    s = re.sub(r"^.*?(10\.\d{4,9}/)", r"\1", doi, flags=re.IGNORECASE)
    return re.sub(r"[).,;'\"\s]+$", "", s).strip()


def _normalize_csl(csl: dict) -> dict:
    if not isinstance(csl, dict):
        raise ExtractionError("Respuesta de metadatos no válida.")
    if isinstance(csl.get("container-title"), list):
        csl["container-title"] = csl["container-title"][0] if csl["container-title"] else None
    csl.setdefault("type", "article-journal")
    return csl


def _meta_content(html: str, key: str) -> str:
    """Lee el content de una <meta name|property=key> (en cualquier orden de atributos)."""
    k = re.escape(key)
    for pat in (
        r'<meta[^>]+(?:property|name)=["\']' + k + r'["\'][^>]*content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']' + k + r'["\']',
    ):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return unescape(m.group(1).strip())
    return ""


def _webpage_csl(html: str, url: str) -> dict:
    """Genera un CSL-JSON tipo 'webpage' a partir de las meta-etiquetas del HTML."""
    titulo = _meta_content(html, "og:title") or _meta_content(html, "citation_title")
    if not titulo:
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        titulo = unescape(m.group(1).strip()) if m else ""
    sitio = _meta_content(html, "og:site_name")
    autor = _meta_content(html, "author") or _meta_content(html, "citation_author")
    fecha = (
        _meta_content(html, "article:published_time")
        or _meta_content(html, "citation_publication_date")
        or _meta_content(html, "citation_date")
        or _meta_content(html, "date")
    )

    csl: dict = {"type": "webpage", "URL": url}
    if titulo:
        csl["title"] = titulo
    if sitio:
        csl["container-title"] = sitio
    if autor:
        csl["author"] = [{"literal": autor}]
    md = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", fecha or "")
    if md:
        csl["issued"] = {"date-parts": [[int(md.group(1)), int(md.group(2)), int(md.group(3))]]}
    elif (my := re.search(r"\b(19|20)\d{2}\b", fecha or "")):
        csl["issued"] = {"date-parts": [[int(my.group(0))]]}
    return csl
