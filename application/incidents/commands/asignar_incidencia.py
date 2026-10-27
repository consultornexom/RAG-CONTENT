"""Caso de uso: asignar un responsable a una incidencia abierta
(Modulo 10). ABIERTA -> ASIGNADA (Incidencia.asignar())."""
from __future__ import annotations

from domain.incidents.entities import Incidencia
from domain.incidents.exceptions import IncidentNotFoundError
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger


class AsignarIncidencia:
    def __init__(self, repository: IncidentRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, incidencia_id: str, responsable: str) -> Incidencia:
        incidencia = self._repository.get(incidencia_id)
        if incidencia is None:
            raise IncidentNotFoundError(incidencia_id)

        incidencia = incidencia.asignar(responsable)
        self._repository.save(incidencia)
        self._audit.record(
            proyecto_id=incidencia.proyecto_id,
            accion="asignar_incidencia",
            valor_anterior=None,
            valor_nuevo=responsable,
            motivo="Asignacion de responsable (Documento Maestro, Modulo 10).",
        )
        return incidencia
