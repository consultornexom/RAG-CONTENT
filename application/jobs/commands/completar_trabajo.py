"""Caso de uso: marcar un trabajo como completado (EJECUTANDO ->
COMPLETADO) -- el caso de uso pesado devolvio sin lanzar ninguna
excepcion. Lo invoca `workers.cola_de_trabajos.ColaDeTrabajos` al
terminar de ejecutarlo."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class CompletarTrabajo:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.completar()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="completar_trabajo",
            valor_anterior=None,
            valor_nuevo=trabajo.estado.value,
            motivo=f"Trabajo '{trabajo.tipo.value}' completado sobre el documento {trabajo.documento_id}.",
        )
        return trabajo
