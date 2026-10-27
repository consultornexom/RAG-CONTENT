"""PDF sin capa de texto (Modulo 4 ya lo enruto asi -- ver
domain.documents.ports.PdfTextLayerDetector): se rasteriza cada pagina
con PyMuPDF (`fitz`) a una imagen PNG y se reconoce pagina por pagina
con `OcrEngine`, igual que RAG STUDIO (mismo dpi=200: suficiente
resolucion para Tesseract sin generar imagenes desproporcionadamente
grandes). Adaptado como codigo propio (ADR-001, seccion 8), no
importado en vivo.

Unico extractor que de verdad invoca `on_progreso` (ver el docstring
de `DocumentExtractor.extract()`): es el unico tramo de Modulo 5/6 que
puede tardar varios segundos POR PAGINA (Tesseract), suficiente para
que la interfaz se congele el tiempo bastante como para que Windows
muestre su aviso nativo de "no responde" si nadie llama
`QApplication.processEvents()` mientras tanto.
"""
from __future__ import annotations

from collections.abc import Callable

import fitz  # PyMuPDF

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.exceptions import ExtractionFailedError
from domain.documents.ocr_table_reconstruction import RangoBajaConfianza
from domain.documents.ports import DocumentExtractor, OcrEngine

_DPI_RASTERIZACION = 200


class PdfOcrExtractor(DocumentExtractor):
    def __init__(self, ocr_engine: OcrEngine):
        self._ocr_engine = ocr_engine

    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        # Complementa a PdfExtractor (Modulo 5): este solo atiende la
        # ruta OCR de un PDF, nunca la de extraccion directa.
        return formato == FormatoDocumento.PDF and tipo_procesamiento == TipoProcesamiento.OCR

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        try:
            documento_pdf = fitz.open(ruta)
        except Exception as exc:  # PyMuPDF no tiene una excepcion propia especifica para "archivo invalido"
            raise ExtractionFailedError(ruta, str(exc)) from exc

        partes: list[str] = []
        advertencias: list[str] = []
        # Modulo 8 (navegacion sincronizada real): mismo calculo de
        # desplazamientos que PdfExtractor -- ver su comentario.
        mapa_paginas: list[int] = []
        # Mismo criterio de desplazamiento que mapa_paginas, pero para
        # los rangos de baja confianza que cada pagina devuelve en su
        # propio sistema de coordenadas (relativo al texto DE ESA
        # pagina) -- hay que sumarles offset_actual para que queden en
        # el sistema de coordenadas del markdown final completo.
        rangos_baja_confianza: list[RangoBajaConfianza] = []
        offset_actual = 0
        total_paginas = documento_pdf.page_count
        try:
            for i, pagina in enumerate(documento_pdf, start=1):
                if on_progreso is not None:
                    on_progreso(i, total_paginas)
                pixmap = pagina.get_pixmap(dpi=_DPI_RASTERIZACION)
                texto, advertencias_pagina, rangos_pagina = self._ocr_engine.image_to_text(pixmap.tobytes("png"))
                texto = texto.strip()
                advertencias.extend(f"Pagina {i}: {adv}" for adv in advertencias_pagina)
                if not texto:
                    advertencias.append(f"La pagina {i} no produjo texto reconocible por OCR.")
                    mapa_paginas.append(offset_actual)
                    continue
                if partes:
                    offset_actual += 2
                mapa_paginas.append(offset_actual)
                rangos_baja_confianza.extend(
                    RangoBajaConfianza(
                        inicio=rango.inicio + offset_actual,
                        fin=rango.fin + offset_actual,
                        confianza=rango.confianza,
                        texto=rango.texto,
                    )
                    for rango in rangos_pagina
                )
                partes.append(texto)
                offset_actual += len(texto)
        finally:
            documento_pdf.close()

        if not partes:
            advertencias.append("Ninguna pagina del PDF produjo texto reconocible por OCR.")
        return ResultadoExtraccion(
            markdown="\n\n".join(partes),
            metodo="ocr_pdf",
            advertencias=advertencias,
            mapa_paginas=mapa_paginas,
            rangos_baja_confianza=rangos_baja_confianza,
        )
