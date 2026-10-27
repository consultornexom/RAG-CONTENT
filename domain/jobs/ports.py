"""Puertos (interfaces) del contexto Trabajos.

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). `TrabajoRepository` opera siempre contra la base de un unico
proyecto (proyecto.db) -- igual que `DocumentRepository`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import EstadoTrabajo, Trabajo


class TrabajoRepository(ABC):
    """Persistencia de trabajos en la base de un proyecto (proyecto.db,
    Documento Maestro seccion 4.5). A diferencia de
    `RevisionRepository`/`AprobacionRepository` (que solo insertan,
    nunca actualizan), `save()` aqui hace upsert -- mismo criterio que
    `DocumentRepository`: un `Trabajo` es un registro que muta a lo
    largo de su propio ciclo de vida, no un historial acumulado."""

    @abstractmethod
    def save(self, trabajo: Trabajo) -> None: ...

    @abstractmethod
    def get(self, trabajo_id: str) -> Optional[Trabajo]: ...

    @abstractmethod
    def list_by_estado(self, estado: EstadoTrabajo) -> list[Trabajo]: ...

    @abstractmethod
    def list_by_document(self, documento_id: str) -> list[Trabajo]: ...

    @abstractmethod
    def list_pendientes_por_prioridad(self) -> list[Trabajo]:
        """Todos los trabajos en PENDIENTE, ordenados por prioridad
        (URGENTE primero, ver domain.jobs.entities.orden_prioridad) y,
        dentro de la misma prioridad, por `creado_en` ascendente (FIFO)
        -- el orden exacto que
        `workers.cola_de_trabajos.ColaDeTrabajos` necesita para decidir
        cual trabajo despachar primero."""
        ...

    @abstractmethod
    def list(self) -> list[Trabajo]:
        """Definido al final de la clase a proposito: un metodo llamado
        `list` en el cuerpo de la clase oculta al `list` generico de
        Python para cualquier anotacion `list[...]` que aparezca
        DESPUES de el en el mismo cuerpo (con
        `from __future__ import annotations`, mypy resuelve esas
        anotaciones como cadenas en el espacio de nombres de la clase) --
        mismo motivo por el que
        `domain.documents.ports.DocumentRepository.list()` tambien va al
        final."""
        ...
