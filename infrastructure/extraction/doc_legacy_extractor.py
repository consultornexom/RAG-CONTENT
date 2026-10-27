"""DOC legado (formato binario OLE2, Microsoft Word 97-2003): se
convierte primero a DOCX con LibreOffice headless
(domain.documents.ports.LegacyFormatConverter) y luego se reutiliza
DocxExtractor (Modulo 5) sobre el archivo ya convertido -- ADR-001,
seccion 8: 'agregar adaptadores nuevos para DOC/XLS legacy (conversion
previa con LibreOffice headless)'. El directorio temporal de la
conversion se borra siempre (try/finally), exito o fallo, para no
acumular archivos intermedios fuera del arbol del proyecto.
"""
from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.ports import DocumentExtractor, LegacyFormatConverter

from .docx_extractor import DocxExtractor


class DocLegacyExtractor(DocumentExtractor):
    def __init__(self, converter: LegacyFormatConverter, docx_extractor: DocxExtractor | None = None):
        self._converter = converter
        self._docx_extractor = docx_extractor or DocxExtractor()

    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # DOC siempre es EXTRACCION_DIRECTA (Modulo 4) -- el parametro
        # se ignora, igual que DOCX en DocxExtractor.
        return formato == FormatoDocumento.DOC

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        ruta_convertida = self._converter.convertir(ruta, FormatoDocumento.DOCX)
        try:
            resultado = self._docx_extractor.extract(
                ruta_convertida, FormatoDocumento.DOCX, TipoProcesamiento.EXTRACCION_DIRECTA, on_progreso
            )
        finally:
            shutil.rmtree(Path(ruta_convertida).parent, ignore_errors=True)
        return ResultadoExtraccion(
            markdown=resultado.markdown, metodo="doc_legado_via_docx", advertencias=resultado.advertencias
        )
