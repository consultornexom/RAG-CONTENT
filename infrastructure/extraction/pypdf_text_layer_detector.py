"""Adaptador de PdfTextLayerDetector sobre pypdf (ADR-001, seccion 4).

Mismo criterio de deteccion que RAG STUDIO usa en su
`PdfTextExtractor.extract()` (infrastructure/extraction/
text_extractors.py): `page.extract_text()` vacio significa que esa
pagina no tiene capa de texto real -- misma biblioteca (pypdf), mismo
metodo, para no inventar un segundo criterio de "que cuenta como texto"
dentro del mismo par de herramientas hermanas.
"""
from __future__ import annotations

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from domain.documents.exceptions import PdfIllegibleError
from domain.documents.ports import PdfTextLayerDetector


class PyPdfTextLayerDetector(PdfTextLayerDetector):
    def tiene_capa_de_texto(self, ruta: str) -> bool:
        try:
            reader = PdfReader(ruta)
            paginas = reader.pages
            return any((pagina.extract_text() or "").strip() for pagina in paginas)
        except (PyPdfError, OSError, ValueError) as exc:
            raise PdfIllegibleError(ruta, str(exc)) from exc
