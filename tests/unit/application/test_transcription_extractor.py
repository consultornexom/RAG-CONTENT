"""AudioVideoTranscriptionExtractor (Modulo 7) contra un
TranscriptionEngine falso -- a diferencia de test_ocr_extractors.py y
test_legacy_extractors.py, aqui no hay un motor real que ejercitar en
este entorno: faster-whisper necesita descargar los pesos del modelo
desde Hugging Face Hub la primera vez, y el proxy de red de este
entorno de desarrollo bloquea huggingface.co (ver
test_faster_whisper_engine.py, que si confirma ese fallo real). Lo que
se puede y debe probar aqui, con un doble de prueba, es la logica propia
de este extractor: como convierte una lista de Segmento en Markdown con
marcas de tiempo.
"""
from __future__ import annotations

import pytest

from domain.documents.entities import FormatoDocumento, ResultadoTranscripcion, Segmento, TipoProcesamiento
from domain.documents.ports import TranscriptionEngine
from infrastructure.extraction.audio_video_transcription_extractor import AudioVideoTranscriptionExtractor


class _FakeTranscriptionEngine(TranscriptionEngine):
    def __init__(self, resultado: ResultadoTranscripcion):
        self._resultado = resultado

    def transcribir(self, ruta: str) -> ResultadoTranscripcion:
        return self._resultado


@pytest.mark.parametrize(
    "formato", [FormatoDocumento.MP3, FormatoDocumento.WAV, FormatoDocumento.M4A, FormatoDocumento.MP4, FormatoDocumento.MOV]
)
def test_supports_todos_los_formatos_de_audio_video(formato: FormatoDocumento) -> None:
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(ResultadoTranscripcion()))
    assert extractor.supports(formato, TipoProcesamiento.TRANSCRIPCION) is True


def test_no_supports_formatos_no_audio_video() -> None:
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(ResultadoTranscripcion()))
    assert extractor.supports(FormatoDocumento.PDF, TipoProcesamiento.TRANSCRIPCION) is False


def test_segmentos_se_convierten_a_markdown_con_marcas_de_tiempo() -> None:
    resultado = ResultadoTranscripcion(
        segmentos=[
            Segmento(inicio_segundos=0, fin_segundos=5, texto="Hola, bienvenidos a la reunion."),
            Segmento(inicio_segundos=5, fin_segundos=12.5, texto="Hoy vamos a revisar el presupuesto."),
        ]
    )
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(resultado))

    salida = extractor.extract("/tmp/x/reunion.mp3", FormatoDocumento.MP3, TipoProcesamiento.TRANSCRIPCION)

    assert "**[00:00:00 - 00:00:05]** Hola, bienvenidos a la reunion." in salida.markdown
    assert "**[00:00:05 - 00:00:12]** Hoy vamos a revisar el presupuesto." in salida.markdown
    assert salida.metodo == "transcripcion_audio"
    assert salida.advertencias == []


def test_metodo_distingue_audio_de_video() -> None:
    resultado = ResultadoTranscripcion(segmentos=[Segmento(inicio_segundos=0, fin_segundos=1, texto="hola")])
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(resultado))

    salida = extractor.extract("/tmp/x/reunion.mp4", FormatoDocumento.MP4, TipoProcesamiento.TRANSCRIPCION)
    assert salida.metodo == "transcripcion_video"


def test_hablante_se_incluye_en_la_etiqueta_cuando_esta_presente() -> None:
    resultado = ResultadoTranscripcion(
        segmentos=[Segmento(inicio_segundos=0, fin_segundos=3, texto="Buenos dias.", hablante="Hablante 1")]
    )
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(resultado))

    salida = extractor.extract("/tmp/x/entrevista.wav", FormatoDocumento.WAV, TipoProcesamiento.TRANSCRIPCION)
    assert "**[00:00:00 - 00:00:03] Hablante 1:** Buenos dias." in salida.markdown


def test_segmentos_inaudibles_dejan_advertencia_pero_no_fallan() -> None:
    resultado = ResultadoTranscripcion(
        segmentos=[
            Segmento(inicio_segundos=0, fin_segundos=5, texto="Texto claro."),
            Segmento(inicio_segundos=5, fin_segundos=8, texto="", inaudible=True),
        ]
    )
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(resultado))

    salida = extractor.extract("/tmp/x/ruidoso.wav", FormatoDocumento.WAV, TipoProcesamiento.TRANSCRIPCION)
    assert "*(inaudible)*" in salida.markdown
    assert salida.advertencias == ["1 de 2 segmento(s) se marcaron como inaudibles (baja confianza de voz reconocible)."]


def test_sin_segmentos_deja_advertencia() -> None:
    extractor = AudioVideoTranscriptionExtractor(_FakeTranscriptionEngine(ResultadoTranscripcion(segmentos=[])))

    salida = extractor.extract("/tmp/x/silencio.wav", FormatoDocumento.WAV, TipoProcesamiento.TRANSCRIPCION)
    assert salida.markdown == ""
    assert salida.advertencias == ["El archivo no produjo segmentos de audio reconocibles."]
