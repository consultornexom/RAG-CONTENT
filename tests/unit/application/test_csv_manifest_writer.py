from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from domain.documents.entities import FilaManifiesto
from infrastructure.filesystem.csv_manifest_writer import VERSION_ESQUEMA_MANIFIESTO, CsvManifestWriter

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_manifest_writer_test")


@pytest.fixture()
def carpeta():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA / "12_exportaciones"
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _fila(**overrides) -> FilaManifiesto:
    datos = {
        "titulo": "Politica de vacaciones",
        "tipo_fuente": "markdown",
        "ruta_archivo": "doc-1.md",
        "area_propietaria": "rh",
        "nivel_acceso": "interno",
        "idioma": "es",
        "hash_contenido": "e" * 64,
    }
    datos.update(overrides)
    return FilaManifiesto(**datos)


def test_escribir_crea_la_carpeta_y_el_archivo_con_encabezado(carpeta: Path) -> None:
    writer = CsvManifestWriter(carpeta)
    ruta = writer.escribir([])

    assert Path(ruta) == carpeta / "manifiesto.csv"
    with open(ruta, encoding="utf-8", newline="") as archivo:
        filas = list(csv.reader(archivo))
    assert filas[0] == [
        "manifest_schema_version",
        "titulo",
        "tipo_fuente",
        "ruta_archivo",
        "area_propietaria",
        "nivel_acceso",
        "idioma",
        "hash_contenido",
        "vigente_desde",
        "vigente_hasta",
        "autoridad_fuente",
        "sustituye_a",
    ]
    assert len(filas) == 1  # solo encabezado


def test_escribir_incluye_una_fila_por_documento(carpeta: Path) -> None:
    writer = CsvManifestWriter(carpeta)
    writer.escribir([_fila(), _fila(titulo="Otro documento", ruta_archivo="doc-2.md")])

    with open(carpeta / "manifiesto.csv", encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 2
    assert filas[0]["titulo"] == "Politica de vacaciones"
    assert filas[1]["titulo"] == "Otro documento"


def test_escribir_marca_version_2_del_esquema_en_cada_fila(carpeta: Path) -> None:
    """Contrato de intercambio v2 (incidencia real de portabilidad
    2026-09-29): RAG STUDIO distingue un manifiesto nuevo (portable) de
    uno legado por la presencia de esta columna -- ver
    CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md."""
    writer = CsvManifestWriter(carpeta)
    writer.escribir([_fila(), _fila(titulo="Otro documento", ruta_archivo="doc-2.md")])

    with open(carpeta / "manifiesto.csv", encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert all(fila["manifest_schema_version"] == VERSION_ESQUEMA_MANIFIESTO for fila in filas)
    assert VERSION_ESQUEMA_MANIFIESTO == "2"


def test_campos_opcionales_ausentes_se_escriben_como_cadena_vacia(carpeta: Path) -> None:
    writer = CsvManifestWriter(carpeta)
    writer.escribir([_fila()])  # vigente_desde/hasta, autoridad_fuente, sustituye_a en None

    with open(carpeta / "manifiesto.csv", encoding="utf-8", newline="") as archivo:
        fila = next(csv.DictReader(archivo))
    assert fila["vigente_desde"] == ""
    assert fila["vigente_hasta"] == ""
    assert fila["autoridad_fuente"] == ""
    assert fila["sustituye_a"] == ""


def test_escribir_dos_veces_sobrescribe_no_acumula(carpeta: Path) -> None:
    writer = CsvManifestWriter(carpeta)
    writer.escribir([_fila(), _fila(titulo="Segundo")])
    writer.escribir([_fila(titulo="Unico")])

    with open(carpeta / "manifiesto.csv", encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 1
    assert filas[0]["titulo"] == "Unico"
