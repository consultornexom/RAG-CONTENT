"""Despacha al extractor concreto segun FormatoDocumento y
TipoProcesamiento -- unico DocumentExtractor que se cablea en
app.bootstrap; los demas son detalle interno de infrastructure (mismo
patron que CompositeTextExtractor en RAG STUDIO).

Los dos extractores de OCR (Modulo 6) requieren un `OcrEngine` (ver
domain.documents.ports.OcrEngine) -- si no se provee ninguno en
`extractores`, el constructor no puede fabricar uno solo (fabricar un
TesseractOcrEngine con el idioma correcto es responsabilidad de
app.bootstrap, no de este composite), por lo que la lista por defecto
solo cubre extraccion directa; app.bootstrap siempre debe pasar la
lista completa, incluyendo OCR.
"""
from __future__ import annotations

from collections.abc import Callable

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.exceptions import UnsupportedFormatError
from domain.documents.ports import DocumentExtractor

from .csv_extractor import CsvExtractor
from .docx_extractor import DocxExtractor
from .json_extractor import JsonExtractor
from .pdf_extractor import PdfExtractor
from .txt_markdown_extractor import TxtMarkdownExtractor
from .xlsx_extractor import XlsxExtractor


class CompositeDocumentExtractor(DocumentExtractor):
    def __init__(self, extractores: list[DocumentExtractor] | None = None):
        self._extractores = extractores or [
            TxtMarkdownExtractor(),
            JsonExtractor(),
            DocxExtractor(),
            PdfExtractor(),
            XlsxExtractor(),
            CsvExtractor(),
        ]

    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        return any(e.supports(formato, tipo_procesamiento) for e in self._extractores)

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        for extractor in self._extractores:
            if extractor.supports(formato, tipo_procesamiento):
                return extractor.extract(ruta, formato, tipo_procesamiento, on_progreso)
        raise UnsupportedFormatError(ruta, formato.value)
