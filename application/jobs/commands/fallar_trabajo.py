"""Caso de uso: marcar un trabajo como fallido (PREPARANDO o EJECUTANDO
-> FALLIDO), registrando el mensaje de error real. Lo invoca
`workers.cola_de_trabajos.ColaDeTrabajos` cuando el caso de uso pesado
(o su preparacion previa) lanza una excepcion -- nunca se pierde en un
hilo de fondo silencioso, siempre queda en `Trabajo.mensaje_error`."""
from __future__ import annotations

from domain.jobs.entities import Trabajo
from domain.jobs.exceptions import JobNotFoundError
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class FallarTrabajo:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, trabajo_id: str, mensaje_error: str) -> Trabajo:
        trabajo = self._repository.get(trabajo_id)
        if trabajo is None:
            raise JobNotFoundError(trabajo_id)

        trabajo = trabajo.fallar(mensaje_error)
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=trabajo.proyecto_id,
            accion="fallar_trabajo",
            valor_anterior=None,
            valor_nuevo=f"intento {trabajo.intentos}/{trabajo.max_intentos}: {mensaje_error}",
            motivo=f"Trabajo '{trabajo.tipo.value}' fallido sobre el documento {trabajo.documento_id}.",
        )
        return trabajo
