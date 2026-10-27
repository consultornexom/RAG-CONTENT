"""Caso de uso: agregar un documento a un lote (Fase 7). Valida que el
lote exista y siga ABIERTO, y que el documento exista -- mismo patron
de acoplamiento cruzado que `RegistrarIncidencia`/`EncolarTrabajo`, pero
esta vez hacia AMBOS lados: `domain.batches.ports.LoteRepository` (este
mismo contexto) y `domain.documents.ports.DocumentRepository` (el
otro)."""
from __future__ import annotations

from domain.batches.entities import EstadoLote
from domain.batches.exceptions import BatchNotFoundError, LoteCerradoError
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger


class AgregarDocumentoALote:
    def __init__(
        self,
        lote_repository: LoteRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._lote_repository = lote_repository
        self._document_repository = document_repository
        self._audit = audit

    def execute(self, lote_id: str, documento_id: str) -> Documento:
        lote = self._lote_repository.get(lote_id)
        if lote is None:
            raise BatchNotFoundError(lote_id)
        if lote.estado != EstadoLote.ABIERTO:
            raise LoteCerradoError(lote_id)

        documento = self._document_repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        # Hallazgo real de la cuarta auditoria general (2026-08-01):
        # `QuitarDocumentoDeLote` ya bloquea modificar la composicion de
        # un lote CERRADO, pero este caso de uso solo validaba el lote
        # DESTINO -- un documento se podia sacar en silencio de un lote ya
        # CERRADO con solo agregarlo a otro lote ABIERTO, sin pasar nunca
        # por `QuitarDocumentoDeLote` ni por su verificacion. Mismo
        # criterio de "lote huerfano no bloquea mas que uno que si existe"
        # que ya usa `QuitarDocumentoDeLote`.
        if documento.lote_id is not None and documento.lote_id != lote_id:
            lote_origen = self._lote_repository.get(documento.lote_id)
            if lote_origen is not None and lote_origen.estado != EstadoLote.ABIERTO:
                raise LoteCerradoError(documento.lote_id)

        documento = documento.asignar_a_lote(lote_id)
        self._document_repository.save(documento)
        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="agregar_documento_a_lote",
            valor_anterior=None,
            valor_nuevo=f"documento {documento_id} -> lote {lote_id}",
            motivo="Agrupacion de documento en un lote (Documento Maestro, seccion 4.10).",
        )
        return documento
