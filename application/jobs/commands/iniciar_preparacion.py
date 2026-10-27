"""Caso de uso: marcar que la cola tomo un trabajo PENDIENTE y comenzo a
prepararlo (PENDIENTE -> PREPARANDO). Lo invoca
`workers.cola_de_trabajos.ColaDeTrabajos` justo antes de resolver las
dependencias del trabajo (por ejemplo, cargar el documento real), nunca
la interfaz directamente (ADR-001, seccion 4: "workers: puede depender
de application, infrastructure; prohibido: ui")."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class IniciarPreparacion:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.iniciar_preparacion()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="iniciar_preparacion_trabajo",
            valor_anterior=None,
            valor_nuevo=trabajo.estado.value,
            motivo="La cola tomo el trabajo y comenzo a prepararlo (ADR-001, seccion 10).",
        )
        return trabajo
