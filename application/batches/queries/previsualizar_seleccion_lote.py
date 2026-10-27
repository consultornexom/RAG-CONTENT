"""Consulta (no muta nada) para mostrar, ANTES de confirmar, que le
pasaria a cada documento seleccionado si se cerrara un lote con esa
seleccion ahora mismo -- agregado 2026-10-03 a pedido de NEXOM
(Solicitud_Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf, seccion 2:
"Antes de confirmar, mostrar nombre del lote, lista seleccionada y
documentos que cumplen requisitos o presentan bloqueos").

Reusa `application.batches._resolucion.clasificar_para_cierre` -- la
MISMA clasificacion que `CerrarLote` aplica de verdad -- para que esta
vista previa nunca pueda mostrar un resultado distinto del que el
cierre real produciria."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository

from .._resolucion import ResolucionPrevista, clasificar_para_cierre


class PrevisualizarSeleccionLote:
    def __init__(self, document_repository: DocumentRepository, governance: GovernanceService):
        self._document_repository = document_repository
        self._governance = governance

    def execute(self, documento_ids: list[str]) -> list[ResolucionPrevista]:
        """Devuelve una `ResolucionPrevista` por cada id en
        `documento_ids`, en el mismo orden. Lanza
        `domain.documents.exceptions.DocumentNotFoundError` si algun id
        no existe -- nunca lo omite en silencio de la vista previa."""
        resultado: list[ResolucionPrevista] = []
        for documento_id in documento_ids:
            documento = self._document_repository.get(documento_id)
            if documento is None:
                raise DocumentNotFoundError(documento_id)
            resultado.append(clasificar_para_cierre(documento, self._governance))
        return resultado
