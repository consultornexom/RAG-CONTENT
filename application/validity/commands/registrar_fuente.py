"""Caso de uso: registrar (o actualizar) la Fuente de un documento
(Modulo 11, Documento Maestro seccion 4.6, fila 11).

Valida que el documento referenciado exista en el inventario del mismo
proyecto antes de registrar la fuente -- unica dependencia real hacia
el contexto Documentos, resuelta aqui en application (domain.validity
no importa domain.documents en absoluto), mismo patron que
application.incidents.commands.registrar_incidencia.RegistrarIncidencia.

Upsert, no alta estricta: si ya existia una Fuente para este documento,
se actualiza en el mismo registro (Fuente.actualizar()) en vez de
fallar -- el flujo real es "confirmar o corregir", no "registrar una
sola vez" (Documento Maestro, seccion 4.11: paso 9)."""
from __future__ import annotations

from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger
from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository


class RegistrarFuente:
    def __init__(
        self,
        repository: FuenteRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._document_repository = document_repository
        self._audit = audit

    def execute(
        self,
        documento_id: str,
        sistema_origen: str,
        autoridad: str,
        evidencia_consulta: str,
    ) -> Fuente:
        documento = self._document_repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        existente = self._repository.get_by_document(documento_id)
        if existente is not None:
            fuente = existente.actualizar(sistema_origen, autoridad, evidencia_consulta)
        else:
            fuente = Fuente(
                documento_id=documento_id,
                sistema_origen=sistema_origen,
                autoridad=autoridad,
                evidencia_consulta=evidencia_consulta,
            )
        self._repository.save(fuente)
        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="registrar_fuente",
            valor_anterior=None,
            valor_nuevo=f"{fuente.sistema_origen} / {fuente.autoridad}",
            motivo="Alta o actualizacion de la fuente del documento (Documento Maestro, Modulo 11).",
        )
        return fuente
