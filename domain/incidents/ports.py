"""Puertos (interfaces) del contexto Incidencias.

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). `IncidentRepository` opera siempre contra la base de un unico
proyecto (proyecto.db) -- mismo criterio que `DocumentRepository`
(domain.documents.ports), del cual Incidencia depende via `documento_id`
sin que domain.incidents importe domain.documents: esa validacion de
existencia vive en application (ver
application.incidents.commands.registrar_incidencia.RegistrarIncidencia).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import Incidencia


class IncidentRepository(ABC):
    """Persistencia de incidencias en la base de un proyecto
    (proyecto.db, Documento Maestro seccion 4.5)."""

    @abstractmethod
    def save(self, incidencia: Incidencia) -> None: ...

    @abstractmethod
    def get(self, incidencia_id: str) -> Optional[Incidencia]: ...

    @abstractmethod
    def list_by_document(self, documento_id: str) -> list[Incidencia]: ...

    @abstractmethod
    def list(self) -> list[Incidencia]: ...
