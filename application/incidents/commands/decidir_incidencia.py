"""Caso de uso: decidir el desenlace de una incidencia ya respondida
(Modulo 10). RESPONDIDA -> RESUELTA o BLOQUEADA (Incidencia.decidir())."""
from __future__ import annotations

from domain.incidents.entities import Incidencia
from domain.incidents.exceptions import IncidentNotFoundError
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger


class DecidirIncidencia:
    def __init__(self, repository: IncidentRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, incidencia_id: str, decision: str, resuelta: bool) -> Incidencia:
        incidencia = self._repository.get(incidencia_id)
        if incidencia is None:
            raise IncidentNotFoundError(incidencia_id)

        incidencia = incidencia.decidir(decision, resuelta)
        self._repository.save(incidencia)
        self._audit.record(
            proyecto_id=incidencia.proyecto_id,
            accion="decidir_incidencia",
            valor_anterior=None,
            valor_nuevo=f"{incidencia.estado.value}: {decision}",
            motivo="Decision sobre el desenlace de la incidencia (Documento Maestro, Modulo 10).",
        )
        return incidencia
