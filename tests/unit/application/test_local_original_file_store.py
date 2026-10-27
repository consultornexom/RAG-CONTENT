from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from domain.documents.exceptions import OriginalFileCopyError, SourceFileNotFoundError
from infrastructure.filesystem.original_file_store import LocalOriginalFileStore

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_originales_test")


@pytest.fixture()
def entorno():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    origenes = RAIZ_PRUEBA / "origenes"
    originales = RAIZ_PRUEBA / "01_originales"
    origenes.mkdir()
    yield origenes, originales
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_copia_calcula_hash_correcto_y_preserva_contenido(entorno) -> None:
    origenes, originales = entorno
    archivo = origenes / "documento.txt"
    contenido = b"contenido de prueba para el hash"
    archivo.write_bytes(contenido)

    store = LocalOriginalFileStore(originales)
    ruta_copia, hash_sha256, tamano = store.copiar_original(str(archivo))

    assert hash_sha256 == hashlib.sha256(contenido).hexdigest()
    assert tamano == len(contenido)
    assert Path(ruta_copia).read_bytes() == contenido
    assert Path(ruta_copia).parent == originales


def test_archivo_inexistente_falla(entorno) -> None:
    _, originales = entorno
    store = LocalOriginalFileStore(originales)
    with pytest.raises(SourceFileNotFoundError):
        store.copiar_original(str(RAIZ_PRUEBA / "no_existe.txt"))


def test_copia_repetida_del_mismo_archivo_es_idempotente(entorno) -> None:
    origenes, originales = entorno
    archivo = origenes / "documento.txt"
    archivo.write_bytes(b"mismo contenido")

    store = LocalOriginalFileStore(originales)
    primera = store.copiar_original(str(archivo))
    segunda = store.copiar_original(str(archivo))

    assert primera == segunda


def test_fallo_de_copia_lanza_error_de_dominio(entorno, monkeypatch) -> None:
    origenes, originales = entorno
    archivo = origenes / "documento.txt"
    archivo.write_bytes(b"contenido")

    def _copy2_que_falla(*_args, **_kwargs):
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(shutil, "copy2", _copy2_que_falla)

    store = LocalOriginalFileStore(originales)
    with pytest.raises(OriginalFileCopyError):
        store.copiar_original(str(archivo))
