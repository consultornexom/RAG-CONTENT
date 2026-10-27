"""Caso de uso: marcar que el caso de uso pesado esta a punto de
invocarse de verdad (PREPARANDO -> EJECUTANDO). Lo invoca
`workers.cola_de_trabajos.ColaDeTrabajos` inmediatamente antes de llamar
al metodo real de `DocumentsService` correspondiente al `TipoTrabajo`."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class IniciarEjecucion:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.iniciar_ejecucion()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="iniciar_ejecucion_trabajo",
            valor_anterior=None,
            valor_nuevo=trabajo.estado.value,
            motivo="Comienza la ejecucion real del caso de uso pesado (ADR-001, seccion 10).",
        )
        return trabajo
