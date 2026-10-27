"""Caso de uso: quitar un documento de su lote actual (Fase 7). Mismo
criterio de bloqueo que `AgregarDocumentoALote`: no se puede modificar
la composicion de un lote ya CERRADO."""
from __future__ import annotations

from domain.batches.entities import EstadoLote
from domain.batches.exceptions import LoteCerradoError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger


class QuitarDocumentoDeLote:
    def __init__(
        self,
        lote_repository: LoteRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._lote_repository = lote_repository
        self._document_repository = document_repository
        self._audit = audit

    def execute(self, documento_id: str) -> Documento:
        documento = self._document_repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        if documento.lote_id is not None:
            lote = self._lote_repository.get(documento.lote_id)
            # Si el lote referenciado ya no existe (no deberia pasar en
            # el flujo normal), se permite quitar el documento sin
            # lanzar un error de dominio -- limpiar una referencia
            # huerfana nunca deberia estar mas bloqueado que quitarse de
            # un lote que si existe.
            if lote is not None and lote.estado != EstadoLote.ABIERTO:
                raise LoteCerradoError(documento.lote_id)

        documento = documento.quitar_de_lote()
        self._document_repository.save(documento)
        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="quitar_documento_de_lote",
            valor_anterior=None,
            valor_nuevo=f"documento {documento_id}",
            motivo="Se retira el documento de su lote (Documento Maestro, seccion 4.10).",
        )
        return documento
