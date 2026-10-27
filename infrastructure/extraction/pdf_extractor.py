"""PDF con capa de texto: adaptado de RAG STUDIO
(infrastructure/extraction/text_extractors.py: `PdfTextExtractor`) --
copiado y ajustado como codigo propio (ADR-001, seccion 8). Sin el
respaldo de OCR de RAG STUDIO (su Modulo 4): aqui el Modulo 4 de
enrutamiento ya decidio, antes de llegar a este extractor, que el
documento tiene capa de texto real (ver
domain.documents.ports.PdfTextLayerDetector); una pagina individual sin
texto dentro de un documento por lo demas legible se reporta como
advertencia, no se reintenta con OCR (Modulo 6, todavia no
implementado).
"""
from __future__ import annotations

from collections.abc import Callable

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.exceptions import ExtractionFailedError
from domain.documents.ports import DocumentExtractor

from .markdown_helpers import repair_letter_spaced_text


class PdfExtractor(DocumentExtractor):
    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # A diferencia de los demas formatos, un PDF si puede necesitar
        # dos rutas distintas (Modulo 4): este extractor solo atiende la
        # ruta de extraccion directa (capa de texto real); un PDF sin
        # capa de texto lo atiende PdfOcrExtractor (Modulo 6).
        return formato == FormatoDocumento.PDF and tipo_procesamiento == TipoProcesamiento.EXTRACCION_DIRECTA

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: extraer texto ya incrustado en el PDF es
        # inmediato por pagina (a diferencia de PdfOcrExtractor, no hay
        # reconocimiento de imagen de por medio) -- no llega a bloquear
        # la interfaz el tiempo suficiente para justificar el callback.
        try:
            reader = PdfReader(ruta)
            paginas = reader.pages
        except (PyPdfError, OSError, ValueError) as exc:
            raise ExtractionFailedError(ruta, str(exc)) from exc

        partes: list[str] = []
        advertencias: list[str] = []
        # Modulo 8 (navegacion sincronizada real): se registra el
        # desplazamiento donde comenzaria cada pagina DENTRO del
        # Markdown final -- se calcula a mano, en vez de con
        # "\n\n".join(partes) al final, porque solo asi el offset
        # coincide exactamente con el separador que ese join va a
        # insertar entre partes.
        mapa_paginas: list[int] = []
        offset_actual = 0
        for i, pagina in enumerate(paginas, start=1):
            texto = repair_letter_spaced_text((pagina.extract_text() or "").strip())
            if not texto:
                advertencias.append(f"La pagina {i} no produjo texto (posible pagina escaneada).")
                mapa_paginas.append(offset_actual)
                continue
            if partes:
                offset_actual += 2  # separador "\n\n" que el join de abajo va a insertar
            mapa_paginas.append(offset_actual)
            partes.append(texto)
            offset_actual += len(texto)

        if not partes:
            advertencias.append("Ninguna pagina del PDF produjo texto.")
        return ResultadoExtraccion(
            markdown="\n\n".join(partes), metodo="pdf_texto", advertencias=advertencias, mapa_paginas=mapa_paginas
        )
