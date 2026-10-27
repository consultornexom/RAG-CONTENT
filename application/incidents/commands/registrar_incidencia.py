"""Caso de uso: registrar una incidencia sobre un documento (Modulo 10,
Documento Maestro seccion 4.6: "Controlar dudas y defectos"; seccion
4.11.1: "registrar, asignar, resolver o bloquear incidencias").

Valida que el documento referenciado exista en el inventario del mismo
proyecto antes de registrar la incidencia -- unica dependencia real
hacia el contexto Documentos, resuelta aqui en application (domain.
incidents no importa domain.documents en absoluto, ver
domain.incidents.ports.IncidentRepository)."""
from __future__ import annotations

from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.incidents.entities import EtapaIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger


class RegistrarIncidencia:
    def __init__(
        self,
        repository: IncidentRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._document_repository = document_repository
        self._audit = audit

    def execute(
        self,
        proyecto_id: str,
        documento_id: str,
        etapa: EtapaIncidencia,
        tipo: str,
        severidad: SeveridadIncidencia,
        evidencia: str,
        impacto: str,
    ) -> Incidencia:
        documento = self._document_repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        incidencia = Incidencia(
            proyecto_id=proyecto_id,
            documento_id=documento_id,
            etapa=etapa,
            tipo=tipo,
            severidad=severidad,
            evidencia=evidencia,
            impacto=impacto,
        )
        self._repository.save(incidencia)
        self._audit.record(
            proyecto_id=proyecto_id,
            accion="registrar_incidencia",
            valor_anterior=None,
            valor_nuevo=f"{incidencia.tipo} ({incidencia.severidad.value}) sobre documento {documento_id}",
            motivo="Alta de incidencia (Documento Maestro, Modulo 10).",
        )
        return incidencia
