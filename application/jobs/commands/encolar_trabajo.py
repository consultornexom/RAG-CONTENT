"""Caso de uso: encolar un trabajo en segundo plano sobre un documento
(Fase 6, ADR-001 seccion 10; Documento Maestro seccion 4.8).

Valida que el documento referenciado exista en el inventario del mismo
proyecto antes de encolar el trabajo -- unica dependencia real hacia el
contexto Documentos, resuelta aqui en application (domain.jobs no
importa domain.documents en absoluto), mismo patron que
`application.incidents.commands.registrar_incidencia.RegistrarIncidencia`."""
from __future__ import annotations

from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.jobs.entities import Prioridad, Trabajo, TipoTrabajo
from domain.jobs.ports import TrabajoRepository
from domain.projects.ports import AuditLogger


class EncolarTrabajo:
    def __init__(
        self,
        repository: TrabajoRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._document_repository = document_repository
        self._audit = audit

    def execute(
        self,
        proyecto_id: str,
        tipo: TipoTrabajo,
        documento_id: str,
        prioridad: Prioridad = Prioridad.NORMAL,
        max_intentos: int = 3,
    ) -> Trabajo:
        documento = self._document_repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        trabajo = Trabajo(
            proyecto_id=proyecto_id,
            tipo=TipoTrabajo(tipo),
            documento_id=documento_id,
            prioridad=Prioridad(prioridad),
            max_intentos=max_intentos,
        )
        self._repository.save(trabajo)
        self._audit.record(
            proyecto_id=proyecto_id,
            accion="encolar_trabajo",
            valor_anterior=None,
            valor_nuevo=f"{trabajo.tipo.value} sobre documento {documento_id} (prioridad {trabajo.prioridad.value})",
            motivo="Alta de trabajo en la cola en segundo plano (ADR-001, seccion 10).",
        )
        return trabajo
