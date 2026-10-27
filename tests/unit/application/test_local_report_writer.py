"""LocalReportWriter (Fase 8) -- mismo criterio de prueba que
test_csv_manifest_writer.py: carpeta creada al vuelo, encabezados
exactos, sobrescritura determinista, y (aqui ademas) el acta en
Markdown por lote."""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from domain.reports.entities import ActaCierreLote, FilaCalidad, FilaIncidencia, FilaInventario
from infrastructure.filesystem.local_report_writer import LocalReportWriter

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_report_writer_test")


@pytest.fixture()
def carpeta():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA / "10_reportes"
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_escribir_inventario_crea_carpeta_y_encabezado(carpeta: Path) -> None:
    writer = LocalReportWriter(carpeta)
    ruta = writer.escribir_inventario([])

    assert Path(ruta) == carpeta / "informe_inventario.csv"
    with open(ruta, encoding="utf-8", newline="") as archivo:
        filas = list(csv.reader(archivo))
    assert filas[0] == [
        "documento_id",
        "nombre_original",
        "formato",
        "area_propietaria",
        "prioridad",
        "criticidad",
        "estado",
        "vigencia",
    ]


def test_escribir_dos_veces_sobrescribe_no_acumula(carpeta: Path) -> None:
    writer = LocalReportWriter(carpeta)
    fila = FilaInventario(
        documento_id="doc-1",
        nombre_original="a.pdf",
        formato="pdf",
        area_propietaria="",
        prioridad="normal",
        criticidad="no_critico",
        estado="recibido",
        vigencia="desconocida",
    )
    writer.escribir_inventario([fila, fila])
    writer.escribir_inventario([fila])

    with open(carpeta / "informe_inventario.csv", encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 1


def test_listas_se_serializan_unidas_con_punto_y_coma(carpeta: Path) -> None:
    writer = LocalReportWriter(carpeta)
    fila = FilaCalidad(
        documento_id="doc-1",
        estado="recibido",
        advertencias_extraccion=["la pagina 2 no produjo texto"],
        advertencias_markdown=[],
        incumplimientos=["falta Fuente", "falta Aprobacion"],
        semaforo="amarillo",
    )
    writer.escribir_calidad([fila])

    with open(carpeta / "informe_calidad.csv", encoding="utf-8", newline="") as archivo:
        fila_leida = next(csv.DictReader(archivo))
    assert fila_leida["incumplimientos"] == "falta Fuente; falta Aprobacion"
    assert fila_leida["advertencias_extraccion"] == "la pagina 2 no produjo texto"
    assert fila_leida["advertencias_markdown"] == ""


def test_booleanos_se_serializan_en_espanol(carpeta: Path) -> None:
    writer = LocalReportWriter(carpeta)
    fila = FilaIncidencia(
        incidencia_id="inc-1",
        documento_id="doc-1",
        etapa="revision",
        tipo="cifra_dudosa",
        severidad="alta",
        estado="abierta",
        responsable="",
        abierta=True,
    )
    writer.escribir_incidencias([fila])

    with open(carpeta / "informe_incidencias.csv", encoding="utf-8", newline="") as archivo:
        fila_leida = next(csv.DictReader(archivo))
    assert fila_leida["abierta"] == "si"
    assert fila_leida["vencida"] == ""  # None -> cadena vacia


def test_escribir_acta_produce_un_archivo_por_lote(carpeta: Path) -> None:
    writer = LocalReportWriter(carpeta)
    acta_1 = ActaCierreLote(lote_id="lote-1", nombre_lote="Lote 1", liberados=["doc-1"], aprobadores=["ana"])
    acta_2 = ActaCierreLote(lote_id="lote-2", nombre_lote="Lote 2", bloqueados=["doc-2"])

    ruta_1 = writer.escribir_acta_cierre_lote(acta_1)
    ruta_2 = writer.escribir_acta_cierre_lote(acta_2)

    assert ruta_1 != ruta_2
    contenido_1 = Path(ruta_1).read_text(encoding="utf-8")
    assert "doc-1" in contenido_1
    assert "ana" in contenido_1
    contenido_2 = Path(ruta_2).read_text(encoding="utf-8")
    assert "doc-2" in contenido_2
    assert "(ninguno)" in contenido_2  # sin liberados en el lote-2
