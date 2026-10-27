"""Fix real de la tercera auditoria general (2026-07-31), aplicado en la
cuarta ronda de correcciones: `scripts/ejecutar_pruebas_aceptacion.py`
no capturaba errores especificos del dominio (por ejemplo, un perfil
YAML corrupto en la raiz aislada de aceptacion, o un fallo al abrir la
base de datos de esa raiz) -- un error de este tipo dejaba pasar un
traceback completo de Python en la terminal en vez de un mensaje corto
y claro, con codigo de salida 1.

`main()` importa `bootstrap`/`abrir_proyecto` en linea (`from
app.bootstrap import ...`, dentro de la funcion, no via un punto de
entrada separado como en `gestionar_respaldos.py`) -- por eso estas
pruebas monkeypatchean directamente `app.bootstrap.bootstrap`, que es
donde ese import se resuelve en tiempo de ejecucion."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import app.bootstrap
from scripts import ejecutar_pruebas_aceptacion


@pytest.fixture()
def corpus_no_vacio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige `_CORPUS_DOCUMENTOS` (el chequeo de corpus vacio en
    `main()`) y `_RAIZ_ACEPTACION` (donde `_preparar_raiz_aceptacion()`
    escribe) a una carpeta temporal -- para no depender del corpus real
    del repositorio ni escribir en `corpus_aceptacion/_runtime/`."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "documento.txt").write_text("contenido de prueba", encoding="utf-8")
    monkeypatch.setattr(ejecutar_pruebas_aceptacion, "_CORPUS_DOCUMENTOS", corpus_dir)
    monkeypatch.setattr(ejecutar_pruebas_aceptacion, "_RAIZ_ACEPTACION", tmp_path / "_runtime")
    return corpus_dir


def test_bootstrap_que_falla_no_deja_pasar_un_traceback(
    corpus_no_vacio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _bootstrap_que_falla(raiz: str) -> Any:
        raise RuntimeError("no se pudo abrir la base de datos de la raiz de aceptacion")

    monkeypatch.setattr(app.bootstrap, "bootstrap", _bootstrap_que_falla)

    codigo = ejecutar_pruebas_aceptacion.main()

    assert codigo == 1
    salida = capsys.readouterr().out
    assert "no se pudo abrir la base de datos de la raiz de aceptacion" in salida
    assert "Traceback" not in salida


def test_crear_proyecto_que_falla_no_deja_pasar_un_traceback(
    corpus_no_vacio: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _ProjectsQueFalla:
        def crear_proyecto(self, nombre: str, perfil_id: str) -> Any:
            raise ValueError("el perfil 'perfil_generico' no tiene una version valida")

    class _CtxDeProyectosQueFalla:
        def __init__(self) -> None:
            self.projects = _ProjectsQueFalla()

    monkeypatch.setattr(app.bootstrap, "bootstrap", lambda raiz: _CtxDeProyectosQueFalla())

    codigo = ejecutar_pruebas_aceptacion.main()

    assert codigo == 1
    salida = capsys.readouterr().out
    assert "el perfil 'perfil_generico' no tiene una version valida" in salida
    assert "Traceback" not in salida


def test_corpus_vacio_sigue_avisando_sin_pasar_por_el_try(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """El chequeo de corpus vacio es anterior al bloque try/except nuevo
    -- confirma que ese aviso especifico (ya existente) sigue intacto."""
    corpus_vacio = tmp_path / "corpus_vacio"
    corpus_vacio.mkdir()
    monkeypatch.setattr(ejecutar_pruebas_aceptacion, "_CORPUS_DOCUMENTOS", corpus_vacio)

    codigo = ejecutar_pruebas_aceptacion.main()

    assert codigo == 1
    assert "esta vacio" in capsys.readouterr().out
