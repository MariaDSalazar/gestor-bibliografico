"""Casos de uso del contexto Citas (Fase 1)."""

from __future__ import annotations

from ..domain.ports import CitationFormatter


class CitationService:
    def __init__(self, formatter: CitationFormatter):
        self._formatter = formatter

    def reference(self, csl, style: str = "apa") -> str:
        return self._formatter.reference(csl, style)

    def in_text(self, csl: dict, opts: dict) -> str:
        return self._formatter.in_text(csl, opts)
