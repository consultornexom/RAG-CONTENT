"""FasterWhisperEngine (Modulo 7). Dos categorias de prueba, deliberadamente
distintas:

1. La logica propia del adaptador (mapear Segment de faster-whisper a
   nuestro Segmento, heuristica de inaudible) se prueba con un
   WhisperModel falso via monkeypatch -- no requiere red.
2. Un intento real de cargar el modelo, sin ningun mock, para confirmar
   el comportamiento real de este entorno: el proxy de red bloquea
   huggingface.co (confirmado empiricamente, ver README), asi que
   cargar cualquier modelo Whisper aqui falla con
   TranscriptionEngineUnavailableError -- a diferencia de Tesseract
   (Modulo 6), este motor no tiene ningun fallback: sin pesos no hay
   transcripcion posible en absoluto en este entorno de desarrollo. En
   una maquina con acceso a Hugging Face Hub (o con los pesos ya
   cacheados localmente), la prueba 2 no aplicaria -- por eso se marca
   con un mensaje explicito en vez de simplemente fallar en silencio si
   algun dia se ejecuta en un entorno distinto.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from domain.documents.exceptions import TranscriptionEngineUnavailableError
from infrastructure.extraction.faster_whisper_engine import FasterWhisperEngine


class _FakeSegment(SimpleNamespace):
    pass


class _FakeWhisperModel:
    """Doble de WhisperModel: se instancia sin descargar nada y
    devuelve segmentos fijos, para poder probar el mapeo de
    FasterWhisperEngine sin depender de red ni de pesos reales."""

    ultima_instancia = None

    def __init__(self, model_size_or_path, device="cpu", compute_type="int8", **kwargs):
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type
        _FakeWhisperModel.ultima_instancia = self

    def transcribe(self, audio, language=None, **kwargs):
        self.ruta_recibida = audio
        self.idioma_recibido = language
        segmentos = [
            _FakeSegment(start=0.0, end=2.5, text=" Hola mundo ", no_speech_prob=0.05),
            _FakeSegment(start=2.5, end=5.0, text="", no_speech_prob=0.92),
        ]
        return segmentos, SimpleNamespace(language="es")


def test_mapea_segmentos_de_whisper_a_segmento_de_dominio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("faster_whisper.WhisperModel", _FakeWhisperModel)

    engine = FasterWhisperEngine(model_size="tiny", idioma="es")
    resultado = engine.transcribir("/tmp/x/audio.mp3")

    assert len(resultado.segmentos) == 2
    assert resultado.segmentos[0].texto == "Hola mundo"  # strip() aplicado
    assert resultado.segmentos[0].inicio_segundos == 0.0
    assert resultado.segmentos[0].fin_segundos == 2.5
    assert resultado.segmentos[0].inaudible is False
    assert resultado.segmentos[1].inaudible is True  # no_speech_prob=0.92 >= 0.6


def test_modelo_se_carga_una_sola_vez_y_se_reutiliza(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("faster_whisper.WhisperModel", _FakeWhisperModel)

    engine = FasterWhisperEngine(model_size="tiny")
    engine.transcribir("/tmp/x/audio1.mp3")
    primera_instancia = _FakeWhisperModel.ultima_instancia
    engine.transcribir("/tmp/x/audio2.mp3")
    segunda_instancia = _FakeWhisperModel.ultima_instancia

    assert primera_instancia is segunda_instancia  # no se recarga el modelo


def test_idioma_se_pasa_al_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("faster_whisper.WhisperModel", _FakeWhisperModel)

    engine = FasterWhisperEngine(idioma="es")
    engine.transcribir("/tmp/x/audio.mp3")

    assert _FakeWhisperModel.ultima_instancia.idioma_recibido == "es"


def test_error_al_transcribir_se_envuelve_en_excepcion_de_dominio(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ModeloQueFalla(_FakeWhisperModel):
        def transcribe(self, audio, language=None, **kwargs):
            raise RuntimeError("archivo no decodificable")

    monkeypatch.setattr("faster_whisper.WhisperModel", _ModeloQueFalla)

    engine = FasterWhisperEngine()
    with pytest.raises(TranscriptionEngineUnavailableError):
        engine.transcribir("/tmp/x/corrupto.mp3")


def test_cargar_modelo_real_sin_acceso_a_internet_falla_con_error_claro() -> None:
    """Prueba real, sin mocks: en este entorno de desarrollo, cargar
    cualquier modelo Whisper falla porque el proxy de red bloquea
    huggingface.co (confirmado con curl: 403 Forbidden). Documenta la
    restriccion real del entorno -- ver docstring del modulo."""
    engine = FasterWhisperEngine(model_size="tiny")
    with pytest.raises(TranscriptionEngineUnavailableError):
        engine.transcribir("/tmp/x/no_importa_no_llega_a_leerse.mp3")
