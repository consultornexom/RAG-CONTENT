"""Puertos (interfaces) del contexto Lotes.

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). `LoteRepository` opera siempre contra la base de un unico proyecto
(proyecto.db) -- igual que `DocumentRepository`/`TrabajoRepository`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import Lote


class LoteRepository(ABC):
    """Persistencia de lotes en la base de un proyecto (proyecto.db,
    Documento Maestro seccion 4.5). Upsert -- mismo criterio que
    `DocumentRepository`/`TrabajoRepository`: un `Lote` es un registro
    que muta (de ABIERTO a CERRADO), no un historial acumulado.

    No incluye `list_by_document` ni ninguna consulta por documento: la
    relacion Lote-Documento se resuelve del lado de `DocumentRepository.
    list()` filtrando por `Documento.lote_id` en `application.batches`
    (mismo criterio ya usado por `application.documents.commands.
    generar_manifiesto.GenerarManifiesto`, que filtra `DocumentRepository.
    list()` en Python en vez de agregar un metodo de consulta nuevo)."""

    @abstractmethod
    def save(self, lote: Lote) -> None: ...

    @abstractmethod
    def get(self, lote_id: str) -> Optional[Lote]: ...

    @abstractmethod
    def list_by_proyecto(self, proyecto_id: str) -> list[Lote]: ...

    @abstractmethod
    def list(self) -> list[Lote]:
        """Definido al final a proposito: un metodo llamado `list` oculta
        al `list` generico de Python para cualquier anotacion
        `list[...]` que aparezca DESPUES de el en el mismo cuerpo de la
        clase (con `from __future__ import annotations`, mypy resuelve
        esas anotaciones como cadenas en el espacio de nombres de la
        clase) -- mismo motivo documentado en
        domain.jobs.ports.TrabajoRepository.list()."""
        ...
