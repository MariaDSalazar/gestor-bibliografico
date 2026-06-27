"""Conexión a la base de datos con SQLAlchemy.

Un mismo código sirve para SQLite (local/pruebas) y PostgreSQL (producción, Neon):
el motor se elige según la variable de entorno DATABASE_URL.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa de la que heredan todos los modelos (ver models.py)."""


def _default_sqlite_url() -> str:
    data = Path(os.environ.get("BIBLIO_DATA", Path.home() / ".gestor-bibliografico"))
    data.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data / 'bibliografia.db').as_posix()}"


def _normalize(url: str) -> str:
    # Neon/Heroku dan "postgres://"; SQLAlchemy 2 + psycopg necesita "postgresql+psycopg://".
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def make_sessionmaker(url: str | None = None) -> sessionmaker:
    url = _normalize(url or os.environ.get("DATABASE_URL") or _default_sqlite_url())
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)

    from . import models  # noqa: F401  (registra los modelos en Base.metadata)

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
