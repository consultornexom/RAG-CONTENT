"""Caso de uso: cerrar una incidencia ya resuelta o bloqueada
(Modulo 10). RESUELTA/BLOQUEADA -> CERRADA (Incidencia.cerrar())."""
from __future__ import annotations

from domain.incidents.entities import Incidencia
from domain.incidents.exceptions import IncidentNotFoundError
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger


class CerrarIncidencia:
    def __init__(self, repository: IncidentRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, incidencia_id: str, cierre: str) -> Incidencia:
        incidencia = self._repository.get(incidencia_id)
        if incidencia is None:
            raise IncidentNotFoundError(incidencia_id)

        incidencia = incidencia.cerrar(cierre)
        self._repository.save(incidencia)
        self._audit.record(
            proyecto_id=incidencia.proyecto_id,
            accion="cerrar_incidencia",
            valor_anterior=None,
            valor_nuevo=cierre,
            motivo="Cierre de incidencia (Documento Maestro, Modulo 10).",
        )
        return incidencia
