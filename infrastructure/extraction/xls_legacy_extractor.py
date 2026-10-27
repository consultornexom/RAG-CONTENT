"""XLS legado (formato binario, Microsoft Excel 97-2003): se convierte
primero a XLSX con LibreOffice headless
(domain.documents.ports.LegacyFormatConverter) y luego se reutiliza
XlsxExtractor (Modulo 5) sobre el archivo ya convertido -- mismo
principio que DocLegacyExtractor (ver su docstring), ADR-001, seccion
8.
"""
from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.ports import DocumentExtractor, LegacyFormatConverter

from .xlsx_extractor import XlsxExtractor


class XlsLegacyExtractor(DocumentExtractor):
    def __init__(self, converter: LegacyFormatConverter, xlsx_extractor: XlsxExtractor | None = None):
        self._converter = converter
        self._xlsx_extractor = xlsx_extractor or XlsxExtractor()

    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # XLS siempre es EXTRACCION_DIRECTA (Modulo 4) -- el parametro
        # se ignora, igual que XLSX en XlsxExtractor.
        return formato == FormatoDocumento.XLS

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        ruta_convertida = self._converter.convertir(ruta, FormatoDocumento.XLSX)
        try:
            resultado = self._xlsx_extractor.extract(
                ruta_convertida, FormatoDocumento.XLSX, TipoProcesamiento.EXTRACCION_DIRECTA, on_progreso
            )
        finally:
            shutil.rmtree(Path(ruta_convertida).parent, ignore_errors=True)
        return ResultadoExtraccion(
            markdown=resultado.markdown, metodo="xls_legado_via_xlsx", advertencias=resultado.advertencias
        )
