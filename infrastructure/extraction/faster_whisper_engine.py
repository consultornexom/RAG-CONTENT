"""Motor de transcripcion real via Whisper local (faster-whisper) --
ADR-001, seccion 14.1, confirmado 2026-07-28. RAG STUDIO no tiene este
adaptador (no maneja audio/video); es propio de RAG Content Studio
Desktop.

El modelo se carga de forma perezosa (en el primer `transcribir()`, no
en `__init__`) y se cachea en la instancia -- cargarlo implica
descargar pesos (~decenas/cientos de MB segun `model_size`) la primera
vez que se usa, y falla igual de "de verdad" que Tesseract si el
binario/paquete de idioma faltara: sin acceso de red a Hugging Face Hub
no hay pesos que cargar. Confirmado empiricamente en el entorno de
desarrollo de este proyecto que el proxy de red bloquea huggingface.co
(403 Forbidden) -- a diferencia de Tesseract (que sigue funcionando en
ingles aunque falte el paquete de espanol), aqui no existe un
fallback: sin pesos, no hay transcripcion posible en absoluto. Ver
README para el detalle de esta restriccion real de entorno.
"""
from __future__ import annotations

from typing import Any, Optional

from domain.documents.entities import ResultadoTranscripcion, Segmento
from domain.documents.exceptions import TranscriptionEngineUnavailableError
from domain.documents.ports import TranscriptionEngine

_MODELO_POR_DEFECTO = "small"
"""Balance razonable para CPU (ADR-001, seccion 14.2: "GPU no requerida
en v1") entre calidad de reconocimiento y tiempo de procesamiento --
mismo criterio de "recomendacion provisional" que el resto de Modulo
7."""
_IDIOMA_POR_DEFECTO = "es"
"""Espanol (ADR-001, seccion 14.1: "buen soporte de espanol") -- a
diferencia de OCR, aqui no se combina con otro idioma: Whisper detecta
un unico idioma dominante por archivo, no mezcla dos como Tesseract."""
_UMBRAL_NO_SPEECH = 0.6
"""Mismo umbral que faster-whisper usa internamente por defecto
(`no_speech_threshold` en `WhisperModel.transcribe()`) para decidir
segmentacion -- se reutiliza aqui para marcar `Segmento.inaudible`,
manteniendo un solo criterio consistente en vez de inventar uno nuevo."""


class FasterWhisperEngine(TranscriptionEngine):
    def __init__(self, model_size: str = _MODELO_POR_DEFECTO, idioma: str = _IDIOMA_POR_DEFECTO):
        self._model_size = model_size
        self._idioma = idioma
        self._modelo: Optional[Any] = None

    def _obtener_modelo(self) -> Any:
        if self._modelo is not None:
            return self._modelo
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionEngineUnavailableError(
                "El paquete 'faster-whisper' no esta instalado en este entorno."
            ) from exc

        try:
            self._modelo = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        except Exception as exc:
            raise TranscriptionEngineUnavailableError(
                f"No se pudo cargar el modelo Whisper '{self._model_size}' "
                f"(sin acceso de red a Hugging Face Hub, o pesos corruptos/ausentes): {exc}"
            ) from exc
        return self._modelo

    def transcribir(self, ruta: str) -> ResultadoTranscripcion:
        modelo = self._obtener_modelo()
        try:
            segmentos_whisper, _info = modelo.transcribe(ruta, language=self._idioma)
            segmentos = [
                Segmento(
                    inicio_segundos=s.start,
                    fin_segundos=s.end,
                    texto=s.text.strip(),
                    hablante=None,  # Sin diarizacion en la primera version -- ver docstring de Segmento.
                    inaudible=s.no_speech_prob >= _UMBRAL_NO_SPEECH,
                )
                for s in segmentos_whisper
            ]
        except TranscriptionEngineUnavailableError:
            raise
        except Exception as exc:
            raise TranscriptionEngineUnavailableError(
                f"No se pudo transcribir '{ruta}': archivo no decodificable "
                f"(ffmpeg ausente o formato no reconocido) o error del motor: {exc}"
            ) from exc
        return ResultadoTranscripcion(segmentos=segmentos)
