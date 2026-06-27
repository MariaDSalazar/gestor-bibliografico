"""Entidades y value objects del dominio.

El formato canónico de un documento es CSL-JSON: la entidad `Document` lo toma
como fuente de verdad y expone propiedades derivadas para el resto del sistema.
Esta capa NO depende de FastAPI, sqlite, httpx, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Author:
    family: str | None = None
    given: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.given, self.family) if p)


@dataclass
class Document:
    """Aggregate root del contexto Catálogo. `csl` (CSL-JSON) es la fuente de verdad."""

    csl: dict = field(default_factory=dict)
    id: int | None = None
    date_added: str | None = None
    has_pdf: bool = False

    @property
    def type(self) -> str:
        return self.csl.get("type") or "article-journal"

    @property
    def title(self) -> str | None:
        return self.csl.get("title")

    @property
    def doi(self) -> str | None:
        return self.csl.get("DOI")

    @property
    def url(self) -> str | None:
        return self.csl.get("URL")

    @property
    def publisher(self) -> str | None:
        return self.csl.get("publisher")

    @property
    def abstract(self) -> str | None:
        return self.csl.get("abstract")

    @property
    def container_title(self) -> str | None:
        c = self.csl.get("container-title")
        if isinstance(c, list):
            return c[0] if c else None
        return c

    @property
    def year(self) -> int | None:
        parts = (self.csl.get("issued") or {}).get("date-parts") or []
        try:
            return int(parts[0][0])
        except (IndexError, ValueError, TypeError):
            return None

    @property
    def authors(self) -> list[Author]:
        return [Author(a.get("family"), a.get("given")) for a in self.csl.get("author", [])]


@dataclass
class Collection:
    """Carpeta del contexto Organización (soporta jerarquía vía parent_id)."""

    name: str
    id: int | None = None
    parent_id: int | None = None
    doc_count: int = 0


@dataclass
class User:
    """Usuario que es dueño de su propia biblioteca."""

    username: str
    id: int | None = None
    password_hash: str | None = None
