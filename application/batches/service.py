"""Fachada del contexto Lotes (ADR-001, seccion 4: ui solo depende de
application)."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.batches.entities import Lote
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger

from .commands.agregar_documento_a_lote import AgregarDocumentoALote
from .commands.cerrar_lote import CerrarLote
from .commands.crear_lote import CrearLote
from .commands.crear_lote_con_seleccion import CrearLoteConSeleccionYCerrar
from .commands.quitar_documento_de_lote import QuitarDocumentoDeLote
from .queries.previsualizar_seleccion_lote import PrevisualizarSeleccionLote
from ._resolucion import ResolucionPrevista


class BatchesService:
    def __init__(
        self,
        repository: LoteRepository,
        document_repository: DocumentRepository,
        governance: GovernanceService,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._document_repository = document_repository
        self._crear = CrearLote(repository, audit)
        self._agregar = AgregarDocumentoALote(repository, document_repository, audit)
        self._quitar = QuitarDocumentoDeLote(repository, document_repository, audit)
        self._cerrar = CerrarLote(repository, document_repository, governance, audit)
        # Agregado 2026-10-03 (NEXOM, seleccion de documentos al cerrar
        # un lote): compone los tres casos de uso de arriba, no duplica
        # ninguna regla -- ver docstring de CrearLoteConSeleccionYCerrar.
        self._crear_con_seleccion = CrearLoteConSeleccionYCerrar(self._crear, self._agregar, self._cerrar)
        self._previsualizar = PrevisualizarSeleccionLote(document_repository, governance)

    def crear_lote(self, proyecto_id: str, nombre: str) -> Lote:
        return self._crear.execute(proyecto_id, nombre)

    def crear_lote_con_seleccion_y_cerrar(self, proyecto_id: str, nombre: str, documento_ids: list[str]) -> Lote:
        return self._crear_con_seleccion.execute(proyecto_id, nombre, documento_ids)

    def previsualizar_seleccion(self, documento_ids: list[str]) -> list[ResolucionPrevista]:
        return self._previsualizar.execute(documento_ids)

    def agregar_documento(self, lote_id: str, documento_id: str) -> Documento:
        return self._agregar.execute(lote_id, documento_id)

    def quitar_documento(self, documento_id: str) -> Documento:
        return self._quitar.execute(documento_id)

    def cerrar_lote(self, lote_id: str) -> Lote:
        return self._cerrar.execute(lote_id)

    def obtener_lote(self, lote_id: str) -> Lote | None:
        return self._repository.get(lote_id)

    def listar_lotes(self, proyecto_id: str) -> list[Lote]:
        return self._repository.list_by_proyecto(proyecto_id)

    def listar_documentos_del_lote(self, lote_id: str) -> list[Documento]:
        return [d for d in self._document_repository.list() if d.lote_id == lote_id]
