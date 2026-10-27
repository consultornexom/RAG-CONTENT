"""Puertos (interfaces) del contexto Vigencias y fuentes (Modulo 11).

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). Ambos repositorios operan siempre contra la base de un unico
proyecto (proyecto.db) -- mismo criterio que `DocumentRepository`
(domain.documents.ports) e `IncidentRepository` (domain.incidents.ports).
A diferencia de esos dos, aqui `get_by_document`/`save` bastan: no hace
falta `get(id)` ni `list()` porque a lo sumo existe un registro por
documento (ver el docstring de domain.validity.entities)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import Fuente, Vigencia


class FuenteRepository(ABC):
    """Persistencia de la Fuente de un documento (a lo sumo una por
    `documento_id`)."""

    @abstractmethod
    def save(self, fuente: Fuente) -> None: ...

    @abstractmethod
    def get_by_document(self, documento_id: str) -> Optional[Fuente]: ...


class VigenciaRepository(ABC):
    """Persistencia de la Vigencia de un documento (a lo sumo una por
    `documento_id`)."""

    @abstractmethod
    def save(self, vigencia: Vigencia) -> None: ...

    @abstractmethod
    def get_by_document(self, documento_id: str) -> Optional[Vigencia]: ...
