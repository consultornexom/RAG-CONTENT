from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from infrastructure.filesystem.extraction_output_store import LocalExtractionOutputStore

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_extraction_output_test")


@pytest.fixture()
def carpeta():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA / "03_extracciones"
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_guardar_crea_la_carpeta_y_el_archivo(carpeta: Path) -> None:
    store = LocalExtractionOutputStore(carpeta)
    ruta = store.guardar("doc-123", "# Titulo\n\ncontenido")

    assert Path(ruta) == carpeta / "doc-123.md"
    assert Path(ruta).read_text(encoding="utf-8") == "# Titulo\n\ncontenido"


def test_guardar_dos_veces_sobrescribe_el_mismo_documento(carpeta: Path) -> None:
    store = LocalExtractionOutputStore(carpeta)
    store.guardar("doc-123", "version 1")
    ruta = store.guardar("doc-123", "version 2")

    assert Path(ruta).read_text(encoding="utf-8") == "version 2"


def test_guardar_escribe_bytes_utf8_exactos_sin_traducir_fin_de_linea(carpeta: Path) -> None:
    """Incidencia 2026-09-30: en Windows, `write_text` en modo texto
    convertia cada "\n" en "\r\n" y el hash declarado en el manifiesto
    dejaba de coincidir con el .md entregado. El archivo debe contener
    exactamente `markdown.encode("utf-8")` en cualquier sistema operativo."""
    store = LocalExtractionOutputStore(carpeta)
    markdown = "# Titulo\n\nLinea con acento: programación.\nOtra linea.\n"

    ruta = store.guardar("doc-crlf", markdown)

    assert Path(ruta).read_bytes() == markdown.encode("utf-8")


def test_guardar_no_depende_del_modo_texto_de_la_plataforma(carpeta: Path, monkeypatch) -> None:
    """Simula Windows: cualquier escritura en modo texto sin `newline`
    explicito traduce "\n" a "\r\n". El adaptador no debe verse afectado."""
    original_open = Path.open

    def open_como_windows(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "w" in mode and "b" not in mode and newline is None:
            newline = "\r\n"
        return original_open(self, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", open_como_windows)
    store = LocalExtractionOutputStore(carpeta)

    ruta = store.guardar("doc-win", "a\nb\n")

    assert Path(ruta).read_bytes() == b"a\nb\n"
