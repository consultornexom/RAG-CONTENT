"""MarkdownInformeAceptacionWriter (Fase 9) -- a diferencia de
CsvManifestWriter/LocalReportWriter (sobrescriben el mismo archivo),
cada corrida debe quedar archivada por separado."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from domain.acceptance.entities import CriterioDominio, CriterioUmbral, InformeAceptacion
from infrastructure.filesystem.markdown_informe_aceptacion_writer import MarkdownInformeAceptacionWriter

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_informe_aceptacion_writer_test")


@pytest.fixture()
def carpeta():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA / "informes"
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _informe(fecha: str) -> InformeAceptacion:
    return InformeAceptacion(
        fecha=fecha,
        corpus_ruta="/tmp/corpus",
        documentos_evaluados=["a.pdf", "b.pdf"],
        criterios_dominio=[
            CriterioDominio(dominio="Inventario", descripcion="desc", cumplido=True, detalle="2 documentos ok"),
            CriterioDominio(dominio="OCR", descripcion="desc", cumplido=None, detalle="sin corpus para OCR todavia"),
        ],
        criterios_umbral=[
            CriterioUmbral(
                indicador="Documentos con hash", umbral_esperado="100%", valor_observado="100%", cumplido=True
            )
        ],
    )


def test_escribir_crea_la_carpeta_y_el_archivo(carpeta: Path) -> None:
    writer = MarkdownInformeAceptacionWriter(carpeta)
    ruta = writer.escribir(_informe("2026-07-29T10:00:00+00:00"))

    assert Path(ruta).exists()
    assert Path(ruta).parent == carpeta


def test_dos_corridas_distintas_no_se_sobrescriben(carpeta: Path) -> None:
    writer = MarkdownInformeAceptacionWriter(carpeta)
    ruta_1 = writer.escribir(_informe("2026-07-29T10:00:00+00:00"))
    ruta_2 = writer.escribir(_informe("2026-07-29T11:00:00+00:00"))

    assert ruta_1 != ruta_2
    assert Path(ruta_1).exists()
    assert Path(ruta_2).exists()


def test_contenido_incluye_dominios_pendientes_y_umbrales(carpeta: Path) -> None:
    writer = MarkdownInformeAceptacionWriter(carpeta)
    ruta = writer.escribir(_informe("2026-07-29T10:00:00+00:00"))

    contenido = Path(ruta).read_text(encoding="utf-8")
    assert "Inventario -- CUMPLE" in contenido
    assert "OCR -- PENDIENTE" in contenido
    assert "Documentos con hash" in contenido
    assert "a.pdf" in contenido and "b.pdf" in contenido


def test_informe_sin_hallazgos_se_marca_aprobado(carpeta: Path) -> None:
    writer = MarkdownInformeAceptacionWriter(carpeta)
    informe = InformeAceptacion(
        fecha="2026-07-29T10:00:00+00:00",
        corpus_ruta="/tmp/corpus",
        criterios_dominio=[CriterioDominio(dominio="Inventario", descripcion="d", cumplido=True, detalle="ok")],
    )
    ruta = writer.escribir(informe)

    contenido = Path(ruta).read_text(encoding="utf-8")
    assert "APROBADO" in contenido
