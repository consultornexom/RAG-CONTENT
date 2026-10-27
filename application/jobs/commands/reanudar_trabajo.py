"""Caso de uso: reanudar un trabajo pausado (PAUSADO -> PENDIENTE) --
vuelve a hacerlo elegible para que la cola lo despache segun su
prioridad (Documento Maestro, seccion 4.1: "reanudacion")."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class ReanudarTrabajo:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.reanudar()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="reanudar_trabajo",
            valor_anterior=None,
            valor_nuevo=trabajo.estado.value,
            motivo="Reanudacion de un trabajo previamente pausado (Documento Maestro, seccion 4.1).",
        )
        return trabajo
