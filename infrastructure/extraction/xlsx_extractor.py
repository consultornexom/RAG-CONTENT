"""XLSX: adaptado de RAG STUDIO (infrastructure/extraction/
text_extractors.py: `XlsxExtractor`) -- copiado y ajustado como codigo
propio (ADR-001, seccion 8). Cada hoja se convierte en un encabezado
Markdown (su nombre) seguido de una tabla Markdown con sus filas; una
hoja vacia se omite con advertencia.
"""
from __future__ import annotations

from collections.abc import Callable

import openpyxl

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.exceptions import ExtractionFailedError
from domain.documents.ports import DocumentExtractor

from .markdown_helpers import rows_to_markdown_table


def _celda_a_texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


class XlsxExtractor(DocumentExtractor):
    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # XLSX siempre es EXTRACCION_DIRECTA -- el parametro se ignora.
        return formato == FormatoDocumento.XLSX

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: leer celdas ya en memoria es rapido
        # incluso en libros grandes (sin OCR de por medio).
        try:
            libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        except Exception as exc:
            raise ExtractionFailedError(ruta, str(exc)) from exc

        try:
            bloques: list[str] = []
            advertencias: list[str] = []
            for hoja in libro.worksheets:
                filas = [
                    [_celda_a_texto(valor) for valor in fila]
                    for fila in hoja.iter_rows(values_only=True)
                    if any(valor is not None and str(valor).strip() for valor in fila)
                ]
                if not filas:
                    advertencias.append(f"La hoja {hoja.title!r} no tiene datos.")
                    continue
                tabla = rows_to_markdown_table(filas)
                bloques.append(f"## {hoja.title}\n\n{tabla}")
            if not bloques:
                advertencias.append("El libro XLSX no tiene ninguna hoja con datos.")
            return ResultadoExtraccion(markdown="\n\n".join(bloques), metodo="xlsx", advertencias=advertencias)
        finally:
            libro.close()
