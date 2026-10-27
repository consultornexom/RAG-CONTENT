"""Prueba de humo del Modulo 4 (clasificacion y enrutamiento). Usa una
raiz temporal, nunca la ruta real de datos.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from app.bootstrap import abrir_proyecto, bootstrap

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test_clasificacion")


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
    origenes_dir = RAIZ_PRUEBA / "_origenes_de_prueba"
    origenes_dir.mkdir()
    yield RAIZ_PRUEBA, origenes_dir
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_clasificar_pdf_con_texto_real(raiz_temporal) -> None:
    raiz, origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Clasificacion de prueba", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    archivo = origenes_dir / "politica.pdf"
    c = canvas.Canvas(str(archivo))
    c.drawString(100, 700, "Politica de vacaciones -- texto real extraible.")
    c.save()

    documento = pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo))
    clasificado = pctx.documents.clasificar_documento(documento.id)

    assert clasificado.estado.value == "clasificado"
    assert clasificado.tipo_procesamiento.value == "extraccion_directa"

    # Recuperado de proyecto.db (no el objeto en memoria que devolvio
    # clasificar_documento): confirma que tipo_procesamiento realmente
    # se persistio en la base, no solo en el objeto de retorno.
    recuperado = pctx.documents.obtener_documento(documento.id)
    assert recuperado is not None
    assert recuperado.estado.value == "clasificado"
    assert recuperado.tipo_procesamiento.value == "extraccion_directa"


def test_clasificar_imagen_va_a_ocr(raiz_temporal) -> None:
    raiz, origenes_dir = raiz_temporal
    ctx = bootstrap(raiz=str(raiz))
    proyecto = ctx.projects.crear_proyecto(nombre="Clasificacion de imagenes", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    archivo = origenes_dir / "pagina_escaneada.png"
    archivo.write_bytes(b"contenido binario simulado de una imagen png")

    documento = pctx.documents.registrar_documento(proyecto_id=proyecto.id, ruta_origen=str(archivo))
    clasificado = pctx.documents.clasificar_documento(documento.id)

    assert clasificado.tipo_procesamiento.value == "ocr"

    recuperado = pctx.documents.obtener_documento(documento.id)
    assert recuperado is not None
    assert recuperado.tipo_procesamiento.value == "ocr"
