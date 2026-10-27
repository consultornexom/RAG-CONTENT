"""Caso 14 del contrato de intercambio (CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md,
seccion 11): "golden package" -- un paquete identico al que produciria
una corrida real de RAG Content Studio, verificado del lado productor
aqui, y del lado consumidor en el propio RAG STUDIO (mismo fixture,
copia idéntica en ambos repos: tests/fixtures/golden_package_14_entrega_rag_studio/
-- no hay una sola prueba que cruce ambos entornos/virtualenvs, ver
seccion 11 del contrato).

Este archivo NO regenera el fixture (evitaria que una regresion en
GenerarManifiesto/CsvManifestWriter se note aqui -- el fixture debe
quedarse fijo, como un contrato firmado). Lo que verifica es que la
FORMA de ese fixture es exactamente la que el escritor real de esta
version produciria: mismas columnas en el mismo orden, mismo valor de
manifest_schema_version, y ruta_archivo con la forma que _nombre_de_archivo()
exige (solo nombre de archivo, nunca ruta con separadores)."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from infrastructure.filesystem.csv_manifest_writer import VERSION_ESQUEMA_MANIFIESTO, _COLUMNAS

_RUTA_FIXTURE_GOLDEN_PACKAGE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "golden_package_14_entrega_rag_studio"
)


def _leer_filas_del_manifiesto() -> list[dict]:
    with (_RUTA_FIXTURE_GOLDEN_PACKAGE / "manifiesto.csv").open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def test_golden_package_existe_y_tiene_manifiesto_y_al_menos_un_md() -> None:
    assert _RUTA_FIXTURE_GOLDEN_PACKAGE.is_dir(), (
        f"Fixture del golden package no encontrado en {_RUTA_FIXTURE_GOLDEN_PACKAGE}"
    )
    archivos_md = list(_RUTA_FIXTURE_GOLDEN_PACKAGE.glob("*.md"))
    assert len(archivos_md) >= 1


def test_encabezado_del_golden_package_coincide_con_las_columnas_reales_de_csv_manifest_writer() -> None:
    with (_RUTA_FIXTURE_GOLDEN_PACKAGE / "manifiesto.csv").open(encoding="utf-8", newline="") as archivo:
        encabezado = next(csv.reader(archivo))
    assert tuple(encabezado) == _COLUMNAS


def test_todas_las_filas_del_golden_package_declaran_version_2() -> None:
    filas = _leer_filas_del_manifiesto()
    assert filas, "el golden package no trae ninguna fila -- no es representativo de una entrega real"
    assert all(fila["manifest_schema_version"] == VERSION_ESQUEMA_MANIFIESTO for fila in filas)


def test_ruta_archivo_del_golden_package_es_solo_nombre_de_archivo() -> None:
    """Forma exigida por el contrato v2 (nunca una ruta con separadores,
    absoluta o relativa con subcarpetas -- ver seccion 5 del contrato)
    y por _nombre_de_archivo() en generar_manifiesto.py."""
    filas = _leer_filas_del_manifiesto()
    for fila in filas:
        ruta = fila["ruta_archivo"]
        assert ruta, "ruta_archivo no puede venir vacia"
        assert "/" not in ruta and "\\" not in ruta, f"ruta_archivo {ruta!r} no es un nombre de archivo plano"


def test_hash_contenido_del_golden_package_coincide_con_el_archivo_fisico() -> None:
    """El propio fixture debe ser consistente con la verificacion de
    integridad obligatoria (seccion 6 del contrato) que aplica RAG
    STUDIO al importarlo -- si esto fallara aqui, el caso 14 del lado de
    RAG STUDIO (tests/unit/application/test_register_sources_from_folder.py::
    test_caso_14_...) fallaria tambien, por la misma razon."""
    filas = _leer_filas_del_manifiesto()
    for fila in filas:
        ruta_md = _RUTA_FIXTURE_GOLDEN_PACKAGE / fila["ruta_archivo"]
        assert ruta_md.is_file(), f"{fila['ruta_archivo']} referenciado en el manifiesto pero no esta en el paquete"
        hash_real = hashlib.sha256(ruta_md.read_bytes()).hexdigest()
        assert hash_real == fila["hash_contenido"], (
            f"el hash declarado para {fila['ruta_archivo']} no coincide con su contenido real"
        )
