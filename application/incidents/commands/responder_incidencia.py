"""Caso de uso: registrar la respuesta/analisis del responsable sobre
una incidencia ya asignada (Modulo 10). ASIGNADA -> RESPONDIDA
(Incidencia.responder())."""
from __future__ import annotations

from domain.incidents.entities import Incidencia
from domain.incidents.exceptions import IncidentNotFoundError
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger


class ResponderIncidencia:
    def __init__(self, repository: IncidentRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, incidencia_id: str, respuesta: str) -> Incidencia:
        incidencia = self._repository.get(incidencia_id)
        if incidencia is None:
            raise IncidentNotFoundError(incidencia_id)

        incidencia = incidencia.responder(respuesta)
        self._repository.save(incidencia)
        self._audit.record(
            proyecto_id=incidencia.proyecto_id,
            accion="responder_incidencia",
            valor_anterior=None,
            valor_nuevo=respuesta,
            motivo="Respuesta/analisis del responsable (Documento Maestro, Modulo 10).",
        )
        return incidencia
