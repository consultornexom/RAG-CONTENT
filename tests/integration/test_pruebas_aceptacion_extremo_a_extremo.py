"""Prueba de humo de la Fase 9 (pruebas de aceptacion sobre datos
reales). Mismo patron que el resto de tests/smoke/test_*_extremo_a_
extremo.py: bootstrap()/abrir_proyecto() reales, sin fakes -- pero
usando una raiz temporal propia (nunca `corpus_aceptacion/_runtime/`,
que es la que usa la corrida manual real via
`scripts/ejecutar_pruebas_aceptacion.py`) para no ensuciarla ni
depender de su estado.

Corre contra el archivo real del corpus de aceptacion
(`corpus_aceptacion/documentos/plan_estudios_electromecanica.pdf`,
Anexo B del Documento Maestro, confirmado 2026-07-28) -- un PDF con
capa de texto real, no sintetico."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.bootstrap import abrir_proyecto, bootstrap
from application.acceptance.service import AcceptanceService
from infrastructure.filesystem.markdown_informe_aceptacion_writer import MarkdownInformeAceptacionWriter

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test_aceptacion")
_PDF_REAL = (
    Path(__file__).resolve().parents[2] / "corpus_aceptacion" / "documentos" / "plan_estudios_electromecanica.pdf"
)


@pytest.fixture()
def raiz_temporal():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    perfiles_dir = RAIZ_PRUEBA / "perfiles" / "perfil_generico"
    perfiles_dir.mkdir(parents=True)
    shutil.copy(
        Path(__file__).resolve().parents[2] / "perfiles" / "perfil_generico" / "0.1.yaml",
        perfiles_dir / "0.1.yaml",
    )
    corpus_dir = RAIZ_PRUEBA / "corpus"
    corpus_dir.mkdir()
    shutil.copy(_PDF_REAL, corpus_dir / _PDF_REAL.name)
    informes_dir = RAIZ_PRUEBA / "informes"
    informes_dir.mkdir()
    yield RAIZ_PRUEBA, corpus_dir, informes_dir
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_corrida_real_contra_el_pdf_del_corpus(raiz_temporal) -> None:
    raiz, corpus_dir, informes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Aceptacion de prueba", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    acceptance = AcceptanceService(pctx.documents, pctx.validity, pctx.incidents, pctx.batches, pctx.reports, proyecto.id)
    informe = acceptance.ejecutar_pruebas_de_aceptacion(corpus_dir)

    assert informe.documentos_evaluados == ["plan_estudios_electromecanica.pdf"]

    por_dominio = {c.dominio: c for c in informe.criterios_dominio}
    assert por_dominio["Inventario"].cumplido is True
    assert por_dominio["Extraccion"].cumplido is True
    assert por_dominio["Normalizacion"].cumplido is True
    assert por_dominio["Markdown"].cumplido is True
    assert por_dominio["Trazabilidad"].cumplido is True
    assert por_dominio["Liberacion"].cumplido is True
    # El PDF real tiene capa de texto (extraccion directa) -- OCR sigue
    # pendiente por falta de corpus, ver corpus_aceptacion/README.md.
    assert por_dominio["OCR"].cumplido is None

    assert all(c.cumplido for c in informe.criterios_umbral)
    assert informe.aprobado() is True
    assert informe.esta_completo() is False  # OCR/transcripcion/legado siguen pendientes

    writer = MarkdownInformeAceptacionWriter(informes_dir)
    ruta_informe = writer.escribir(informe)
    contenido = Path(ruta_informe).read_text(encoding="utf-8")
    assert "plan_estudios_electromecanica.pdf" in contenido
    assert "APROBADO" in contenido
