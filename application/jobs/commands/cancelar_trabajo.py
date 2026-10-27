"""Caso de uso: cancelar un trabajo que todavia no invoco su caso de
uso pesado (PENDIENTE, PREPARANDO o PAUSADO -> CANCELADO) --
"cancelacion segura" (ADR-001, seccion 10): ver el docstring de
domain.jobs.entities._TRANSICIONES sobre por que EJECUTANDO no admite
esta transicion."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class CancelarTrabajo:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.cancelar()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="cancelar_trabajo",
            valor_anterior=None,
            valor_nuevo=trabajo.estado.value,
            motivo="Cancelacion segura -- el caso de uso pesado nunca se invoco (ADR-001, seccion 10).",
        )
        return trabajo
