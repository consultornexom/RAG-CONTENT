"""CSV: adaptado de RAG STUDIO (infrastructure/extraction/
text_extractors.py: `CsvExtractor`) -- copiado y ajustado como codigo
propio (ADR-001, seccion 8). Se convierte en una sola tabla Markdown;
el delimitador se detecta automaticamente (coma/punto y coma/tabulador)
con respaldo a coma si la deteccion falla.
"""
from __future__ import annotations

import csv
from collections.abc import Callable

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.ports import DocumentExtractor

from .markdown_helpers import rows_to_markdown_table


class CsvExtractor(DocumentExtractor):
    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # CSV siempre es EXTRACCION_DIRECTA -- el parametro se ignora.
        return formato == FormatoDocumento.CSV

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: leer un CSV es rapido incluso en
        # archivos grandes (sin OCR de por medio).
        # utf-8-sig: descarta el BOM tipico de un CSV exportado por
        # Excel en Windows en vez de dejarlo colarse en el primer
        # encabezado.
        with open(ruta, encoding="utf-8-sig", errors="replace", newline="") as archivo:
            muestra = archivo.read(4096)
            archivo.seek(0)
            try:
                dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
            except csv.Error:
                dialecto = csv.excel
            filas = [fila for fila in csv.reader(archivo, dialecto) if any(celda.strip() for celda in fila)]

        if not filas:
            return ResultadoExtraccion(markdown="", metodo="csv", advertencias=["El archivo CSV no tiene filas con datos."])
        return ResultadoExtraccion(markdown=rows_to_markdown_table(filas), metodo="csv", advertencias=[])
