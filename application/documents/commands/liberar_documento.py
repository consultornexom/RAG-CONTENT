"""Caso de uso del Modulo 12/13: liberar un documento ya validado --
VALIDADO -> LIBERADO. Es el ultimo paso del flujo principal (Documento
Maestro, seccion 4.7): a partir de aqui el documento queda listo para
que el operador lo entregue manualmente a RAG STUDIO (seccion 4.6.1).

Antes de avanzar el estado, pide a `GovernanceService` que verifique
"no liberar contenido sin fuente, hash y aprobacion" -- el hash ya esta
garantizado por construccion (ver domain.documents.entities.Documento.
liberar()); este caso de uso deja que la verificacion de Fuente/
Aprobacion se propague sin mutar nada si falla, mismo principio que
RevisarDocumento/AprobarParaMarkdown con las otras dos reglas de
Modulo 13."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.documents.entities import Documento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger


class LiberarDocumento:
    def __init__(self, repository: DocumentRepository, audit: AuditLogger, governance: GovernanceService):
        self._repository = repository
        self._audit = audit
        self._governance = governance

    def execute(self, documento_id: str) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        self._governance.verificar_documento_liberable(documento_id)

        documento = documento.liberar()
        self._repository.save(documento)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="liberar_documento",
            valor_anterior=None,
            valor_nuevo=documento.estado.value,
            motivo="Liberacion del documento -- listo para entregarse manualmente a RAG STUDIO "
            "(Documento Maestro, seccion 4.6.1).",
        )
        return documento
