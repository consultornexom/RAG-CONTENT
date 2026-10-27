"""Caso de uso: reintentar un trabajo fallido (FALLIDO -> PENDIENTE),
solo si todavia no agoto `max_intentos` (Documento Maestro, seccion 4.1:
"reintentos"). Deja que `domain.jobs.entities.Trabajo.reintentar()`
lance `ReintentosAgotadosError` sin capturarla -- quien llama decide
como informarlo (por ejemplo, la GUI de la Fase 11)."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class ReintentarTrabajo:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.reintentar()
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="reintentar_trabajo",
            valor_anterior=None,
            valor_nuevo=f"intento {trabajo.intentos + 1}/{trabajo.max_intentos}",
            motivo="Reintento manual de un trabajo fallido (Documento Maestro, seccion 4.1).",
        )
        return trabajo
