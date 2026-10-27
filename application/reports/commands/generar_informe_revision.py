"""Caso de uso de Fase 8: "Informe de revision" (Documento Maestro,
seccion 7.1: "Documentos, responsables, fechas, cobertura y
observaciones").

`domain.documents.ports.RevisionRepository` no tiene un `list()` propio
(solo `list_by_document()`, ver su docstring: cada `Revision` pertenece a
un documento, se consulta siempre desde ahi) -- este caso de uso itera
`DocumentRepository.list()` y junta el historial de cada uno, mismo
patron ya usado por `BatchesService.listar_documentos_del_lote()`."""
from __future__ import annotations

from domain.documents.ports import DocumentRepository, RevisionRepository
from domain.reports.entities import FilaRevision
from domain.reports.ports import ReportWriter


class GenerarInformeRevision:
    def __init__(
        self, document_repository: DocumentRepository, revision_repository: RevisionRepository, writer: ReportWriter
    ):
        self._document_repository = document_repository
        self._revision_repository = revision_repository
        self._writer = writer

    def execute(self) -> str:
        """Devuelve la ruta absoluta del informe escrito. Un documento
        que nunca se reviso simplemente no aporta ningun renglon -- este
        informe es del HISTORIAL de revisiones, no del inventario
        completo (a diferencia del informe de inventario/procesamiento)."""
        filas: list[FilaRevision] = []
        for documento in self._document_repository.list():
            for revision in self._revision_repository.list_by_document(documento.id):
                filas.append(
                    FilaRevision(
                        documento_id=documento.id,
                        revisor=revision.revisor,
                        fecha=revision.fecha.isoformat(),
                        incidencias_detectadas=len(revision.incidencias_detectadas),
                        comentario=revision.comentario,
                    )
                )
        return self._writer.escribir_revision(filas)
