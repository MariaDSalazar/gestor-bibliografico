"""Excepciones de dominio. Se mapean a códigos HTTP en la capa de interfaces."""

from __future__ import annotations


class DomainError(Exception):
    """Error base del dominio."""


class NotFoundError(DomainError):
    """Recurso inexistente → HTTP 404."""


class ValidationError(DomainError):
    """Entrada inválida → HTTP 400."""


class ExtractionError(DomainError):
    """Fallo de extracción mostrable al usuario → HTTP 422."""
