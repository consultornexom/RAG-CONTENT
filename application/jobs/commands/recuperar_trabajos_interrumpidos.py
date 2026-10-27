"""Caso de uso: recuperar los trabajos huerfanos tras un cierre no
controlado de la aplicacion (Documento Maestro, seccion 4.1:
"recuperacion"). Se ejecuta una sola vez, automaticamente, al abrir un
proyecto (`app.bootstrap.abrir_proyecto()`) -- mismo principio de "el
operador nunca lo ejecuta a mano" que ya aplica
`infrastructure.database.migrations.upgrade_to_head()`.

Un trabajo que quedo en PREPARANDO o EJECUTANDO cuando la aplicacion se
cerro ya no tiene ningun hilo real corriendolo -- no hay forma de saber,
desde aqui, si el caso de uso subyacente llego a completarse antes del
cierre. Marcarlo como completado seria optimista sin evidencia; dejarlo
"ejecutando" para siempre seria un trabajo fantasma que nunca se puede
volver a tomar. La opcion honesta es la que aplica
`domain.jobs.entities.Trabajo.marcar_interrumpido()`: FALLIDO, con un
mensaje explicito que pide revision manual antes de reintentar."""
from __future__ import annotations

from domain.jobs.entities import EstadoTrabajo, Trabajo
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class RecuperarTrabajosInterrumpidos:
    def __init__(self, repository: TrabajoRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self) -> list[Trabajo]:
        huerfanos = self._repository.list_by_estado(EstadoTrabajo.PREPARANDO) + self._repository.list_by_estado(
            EstadoTrabajo.EJECUTANDO
        )
        recuperados = []
        for trabajo in huerfanos:
            trabajo = trabajo.marcar_interrumpido()
            self._repository.save(trabajo)
            self._audit.record(
                proyecto_id=trabajo.proyecto_id,
                accion="recuperar_trabajo_interrumpido",
                valor_anterior=None,
                valor_nuevo=trabajo.estado.value,
                motivo="Trabajo huerfano tras un cierre no controlado de la aplicacion "
                "(Documento Maestro, seccion 4.1: 'recuperacion').",
            )
            recuperados.append(trabajo)
        return recuperados
