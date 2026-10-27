"""Audio/video (Modulo 7): siempre van a TRANSCRIPCION (Modulo 4 los
enruta asi sin ambiguedad, igual que las imagenes a OCR -- ver
application.documents.commands.clasificar_documento). Convierte los
`Segmento` que devuelve `TranscriptionEngine` a Markdown con marcas de
tiempo legibles, mismo contrato de salida que el resto de Modulo 5/6
exige para 03_extracciones/ del proyecto (Documento Maestro, seccion
4.6.1: sin YAML embebido, texto plano normalizado).
"""
from __future__ import annotations

from collections.abc import Callable

from domain.documents.entities import FormatoDocumento, ResultadoExtraccion, TipoProcesamiento
from domain.documents.ports import DocumentExtractor, TranscriptionEngine

_SOPORTADOS = {
    FormatoDocumento.MP3,
    FormatoDocumento.WAV,
    FormatoDocumento.M4A,
    FormatoDocumento.MP4,
    FormatoDocumento.MOV,
}


def _formatear_marca(segundos: float) -> str:
    horas, resto = divmod(int(segundos), 3600)
    minutos, segs = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


class AudioVideoTranscriptionExtractor(DocumentExtractor):
    def __init__(self, transcription_engine: TranscriptionEngine):
        self._transcription_engine = transcription_engine

    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool:
        return formato in _SOPORTADOS

    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        # on_progreso se ignora: TranscriptionEngine.transcribir() (Modulo
        # 7, faster-whisper) puede ser tan lento o mas que el OCR de un
        # PDF, pero no expone hoy ningun gancho de progreso por segmento
        # -- no se resuelve en este fix (alcance acotado al hallazgo
        # concreto reportado, OCR de PDF); queda pendiente si se reporta
        # el mismo sintoma con audio/video.
        resultado = self._transcription_engine.transcribir(ruta)

        bloques: list[str] = []
        segmentos_inaudibles = 0
        for segmento in resultado.segmentos:
            marca = f"[{_formatear_marca(segmento.inicio_segundos)} - {_formatear_marca(segmento.fin_segundos)}]"
            etiqueta = f"**{marca} {segmento.hablante}:**" if segmento.hablante else f"**{marca}**"
            if segmento.inaudible:
                segmentos_inaudibles += 1
                texto = segmento.texto or "*(inaudible)*"
            else:
                texto = segmento.texto
            bloques.append(f"{etiqueta} {texto}")

        advertencias: list[str] = []
        if not resultado.segmentos:
            advertencias.append("El archivo no produjo segmentos de audio reconocibles.")
        elif segmentos_inaudibles:
            advertencias.append(
                f"{segmentos_inaudibles} de {len(resultado.segmentos)} segmento(s) "
                "se marcaron como inaudibles (baja confianza de voz reconocible)."
            )

        metodo = "transcripcion_video" if formato in (FormatoDocumento.MP4, FormatoDocumento.MOV) else "transcripcion_audio"
        return ResultadoExtraccion(markdown="\n\n".join(bloques), metodo=metodo, advertencias=advertencias)
