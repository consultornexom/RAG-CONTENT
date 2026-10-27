from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from domain.documents.exceptions import PdfIllegibleError
from infrastructure.extraction.pypdf_text_layer_detector import PyPdfTextLayerDetector

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_pdf_detector_test")


@pytest.fixture()
def raiz():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def _pdf_con_texto(ruta: Path) -> None:
    c = canvas.Canvas(str(ruta))
    c.drawString(100, 700, "Documento con capa de texto real para la prueba.")
    c.save()


def _pdf_sin_texto(ruta: Path) -> None:
    # Una pagina en blanco (sin contenido de texto) simula un PDF
    # escaneado sin OCR aplicado -- pypdf no tiene nada que extraer.
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with ruta.open("wb") as f:
        writer.write(f)


def test_pdf_con_texto_es_detectado(raiz: Path) -> None:
    ruta = raiz / "con_texto.pdf"
    _pdf_con_texto(ruta)

    detector = PyPdfTextLayerDetector()
    assert detector.tiene_capa_de_texto(str(ruta)) is True


def test_pdf_sin_texto_es_detectado(raiz: Path) -> None:
    ruta = raiz / "sin_texto.pdf"
    _pdf_sin_texto(ruta)

    detector = PyPdfTextLayerDetector()
    assert detector.tiene_capa_de_texto(str(ruta)) is False


def test_pdf_ilegible_lanza_excepcion_de_dominio(raiz: Path) -> None:
    ruta = raiz / "no_es_un_pdf.pdf"
    ruta.write_bytes(b"esto no es un PDF valido, solo texto plano")

    detector = PyPdfTextLayerDetector()
    with pytest.raises(PdfIllegibleError):
        detector.tiene_capa_de_texto(str(ruta))
