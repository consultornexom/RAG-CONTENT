"""Caso de uso: clasificar un documento inventariado y enrutarlo hacia
la ruta de procesamiento que le corresponde (Modulo 4, Documento
Maestro seccion 4.6: "Clasificacion y enrutamiento").
"""
from __future__ import annotations

from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError, PdfIllegibleError
from domain.documents.ports import DocumentRepository, PdfTextLayerDetector
from domain.projects.ports import AuditLogger

_SIEMPRE_OCR = {FormatoDocumento.PNG, FormatoDocumento.JPG}
"""Las imagenes no tienen otra ruta de extraccion posible (Documento
Maestro, seccion 4.6, Modulo 4: "imagenes" -> OCR)."""

_SIEMPRE_TRANSCRIPCION = {
    FormatoDocumento.MP3,
    FormatoDocumento.WAV,
    FormatoDocumento.M4A,
    FormatoDocumento.MP4,
    FormatoDocumento.MOV,
}
"""Audio/video no tienen otra ruta de extraccion posible (Modulo 7,
confirmado 2026-07-28 al salir de "extension posterior", Documento
Maestro seccion 4.4)."""


class ClasificarDocumento:
    def __init__(
        self,
        repository: DocumentRepository,
        pdf_detector: PdfTextLayerDetector,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._pdf_detector = pdf_detector
        self._audit = audit

    def _decidir_ruta(self, documento: Documento) -> TipoProcesamiento:
        if documento.formato in _SIEMPRE_OCR:
            return TipoProcesamiento.OCR

        if documento.formato in _SIEMPRE_TRANSCRIPCION:
            return TipoProcesamiento.TRANSCRIPCION

        if documento.formato == FormatoDocumento.PDF:
            try:
                tiene_texto = self._pdf_detector.tiene_capa_de_texto(documento.ruta_copia_original)
            except PdfIllegibleError:
                return TipoProcesamiento.CORRECCION_MANUAL
            return TipoProcesamiento.EXTRACCION_DIRECTA if tiene_texto else TipoProcesamiento.OCR

        # DOCX/DOC/XLSX/XLS/CSV/TXT/MARKDOWN/JSON: sin ambiguedad --
        # si el archivo esta corrupto, fallara en la extraccion real
        # (Modulo 5), no aqui; clasificar solo decide la ruta prevista.
        return TipoProcesamiento.EXTRACCION_DIRECTA

    def execute(self, documento_id: str) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        tipo_procesamiento = self._decidir_ruta(documento)
        documento = documento.clasificar(tipo_procesamiento)

        self._repository.save(documento)
        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="clasificar_documento",
            valor_anterior=EstadoDocumento.INVENTARIADO.value,
            valor_nuevo=tipo_procesamiento.value,
            motivo="Enrutamiento automatico segun formato y capa de texto (Documento Maestro, Modulo 4).",
        )
        return documento
