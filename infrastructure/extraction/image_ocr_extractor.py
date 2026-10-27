"""PNG/JPG: siempre van a OCR (Modulo 4 las enruta asi sin ambiguedad --
una imagen nunca tiene "capa de texto"), asi que este extractor ignora
`tipo_procesamiento` en `supports()` igual que los formatos sin
ambiguedad de Modulo 5. Adaptado del reparto de responsabilidades de
RAG STUDIO: el extractor solo lee bytes y delega el reconocimiento en
si a `OcrEngine` (Tesseract) -- no conoce pytesseract directamente.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.exceptions import ExtractionFailedError
from domain.documents.ports import DocumentExtractor, OcrEngine

_SOPORTADOS = {FormatoDocumento.PNG, FormatoDocumento.JPG}


class ImageOcrExtractor(DocumentExtractor):
    def __init__(self, ocr_engine: OcrEngine):
        self._ocr_engine = ocr_engine

    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        return formato in _SOPORTADOS

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: una sola imagen no tiene sub-unidades
        # (paginas) sobre las que reportar avance parcial -- a
        # diferencia de PdfOcrExtractor, aqui el OCR es una sola llamada.
        try:
            image_bytes = Path(ruta).read_bytes()
        except OSError as exc:
            raise ExtractionFailedError(ruta, str(exc)) from exc

        texto, advertencias, rangos_baja_confianza = self._ocr_engine.image_to_text(image_bytes)
        if not texto.strip():
            advertencias = [*advertencias, "El OCR no reconocio texto en la imagen."]
        return ResultadoExtraccion(
            markdown=texto, metodo="ocr_imagen", advertencias=advertencias, rangos_baja_confianza=rangos_baja_confianza
        )
