"""Caso de uso: pausar un trabajo todavia PENDIENTE (PENDIENTE ->
PAUSADO) -- lo retiene fuera de la cola sin cancelarlo (Documento
Maestro, seccion 4.1: "pausa")."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class PausarTrabajo:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.pausar()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="pausar_trabajo",
            valor_anterior=None,
            valor_nuevo=trabajo.estado.value,
            motivo="Pausa solicitada sobre un trabajo todavia no despachado (Documento Maestro, seccion 4.1).",
        )
        return trabajo
