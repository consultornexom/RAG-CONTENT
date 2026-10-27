"""ImageOcrExtractor y PdfOcrExtractor (Modulo 6) contra un
TesseractOcrEngine real (lang='eng': el unico paquete de idioma
instalado en este entorno de pruebas, ver test_tesseract_ocr_engine.py)
-- no un doble de prueba del motor OCR, porque lo que estas pruebas
necesitan verificar es la integracion real: rasterizacion con PyMuPDF,
lectura de bytes de imagen, y el reparto de responsabilidades con
OcrEngine (ADR-001, seccion 8).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from domain.documents.entities import FormatoDocumento, TipoProcesamiento
from infrastructure.extraction.image_ocr_extractor import ImageOcrExtractor
from infrastructure.extraction.pdf_ocr_extractor import PdfOcrExtractor
from infrastructure.extraction.tesseract_ocr_engine import TesseractOcrEngine

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_ocr_extractores_test")
_FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@pytest.fixture()
def raiz():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    yield RAIZ_PRUEBA
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


@pytest.fixture()
def motor_ocr() -> TesseractOcrEngine:
    return TesseractOcrEngine(lang="eng")


def _imagen_con_texto(ruta: Path, texto: str) -> None:
    fuente = ImageFont.truetype(_FUENTE, 40)
    imagen = Image.new("RGB", (600, 100), color="white")
    ImageDraw.Draw(imagen).text((10, 10), texto, font=fuente, fill="black")
    imagen.save(ruta)


def test_image_ocr_extractor_supports_png_y_jpg(motor_ocr: TesseractOcrEngine) -> None:
    extractor = ImageOcrExtractor(motor_ocr)
    assert extractor.supports(FormatoDocumento.PNG, TipoProcesamiento.OCR) is True
    assert extractor.supports(FormatoDocumento.JPG, TipoProcesamiento.OCR) is True
    assert extractor.supports(FormatoDocumento.PDF, TipoProcesamiento.OCR) is False
    # PNG/JPG siempre van a OCR -- no hay ruta de extraccion directa,
    # asi que tipo_procesamiento se ignora en supports().
    assert extractor.supports(FormatoDocumento.PNG, TipoProcesamiento.EXTRACCION_DIRECTA) is True


def test_image_ocr_extractor_reconoce_texto_real(raiz: Path, motor_ocr: TesseractOcrEngine) -> None:
    ruta = raiz / "escaneo.png"
    _imagen_con_texto(ruta, "HELLO WORLD")

    resultado = ImageOcrExtractor(motor_ocr).extract(str(ruta), FormatoDocumento.PNG, TipoProcesamiento.OCR)
    assert "HELLO WORLD" in resultado.markdown
    assert resultado.metodo == "ocr_imagen"
    assert resultado.advertencias == []
    # Texto nitido y grande -- no hay motivo para que Tesseract dude,
    # asi que no deberia haber ningun rango de baja confianza que
    # propagar (ver test_ocr_table_reconstruction.py para la logica de
    # deteccion en si, con datos controlados).
    assert resultado.rangos_baja_confianza == []


def test_image_ocr_extractor_imagen_sin_texto_deja_advertencia(raiz: Path, motor_ocr: TesseractOcrEngine) -> None:
    ruta = raiz / "en_blanco.png"
    Image.new("RGB", (100, 40), color="white").save(ruta)

    resultado = ImageOcrExtractor(motor_ocr).extract(str(ruta), FormatoDocumento.PNG, TipoProcesamiento.OCR)
    assert resultado.markdown == ""
    assert resultado.advertencias


def test_pdf_ocr_extractor_supports_solo_la_ruta_ocr(motor_ocr: TesseractOcrEngine) -> None:
    extractor = PdfOcrExtractor(motor_ocr)
    assert extractor.supports(FormatoDocumento.PDF, TipoProcesamiento.OCR) is True
    # A diferencia de PNG/JPG, un PDF si puede necesitar la otra ruta
    # (PdfExtractor, Modulo 5) -- este extractor no debe reclamarla.
    assert extractor.supports(FormatoDocumento.PDF, TipoProcesamiento.EXTRACCION_DIRECTA) is False
    assert extractor.supports(FormatoDocumento.PNG, TipoProcesamiento.OCR) is False


def test_pdf_ocr_extractor_rasteriza_y_reconoce_cada_pagina(raiz: Path, motor_ocr: TesseractOcrEngine) -> None:
    imagen_pagina1 = raiz / "pagina1.png"
    imagen_pagina2 = raiz / "pagina2.png"
    _imagen_con_texto(imagen_pagina1, "PRIMERA PAGINA")
    _imagen_con_texto(imagen_pagina2, "SEGUNDA PAGINA")

    ruta_pdf = raiz / "escaneado.pdf"
    documento_pdf = fitz.open()
    for imagen in (imagen_pagina1, imagen_pagina2):
        pagina = documento_pdf.new_page()
        rect = pagina.rect
        pagina.insert_image(rect, filename=str(imagen))
    documento_pdf.save(str(ruta_pdf))
    documento_pdf.close()

    resultado = PdfOcrExtractor(motor_ocr).extract(str(ruta_pdf), FormatoDocumento.PDF, TipoProcesamiento.OCR)
    assert "PRIMERA PAGINA" in resultado.markdown
    assert "SEGUNDA PAGINA" in resultado.markdown
    assert resultado.metodo == "ocr_pdf"
    assert resultado.advertencias == []
    assert len(resultado.mapa_paginas) == 2
    assert resultado.mapa_paginas[0] == 0
    segundo_offset = resultado.mapa_paginas[1]
    assert "SEGUNDA PAGINA" in resultado.markdown[segundo_offset:]
    # Texto nitido y grande en ambas paginas -- no deberia haber ningun
    # rango de baja confianza que propagar (mismo criterio que arriba).
    assert resultado.rangos_baja_confianza == []


def test_pdf_ocr_extractor_invoca_on_progreso_una_vez_por_pagina(raiz: Path, motor_ocr: TesseractOcrEngine) -> None:
    """Corregido 2026-07-31 (captura real del consultor: un
    QProgressDialog completamente en negro con los botones nativos de
    Windows "Forzar la salida"/"Esperar" durante el OCR de un solo
    documento): `on_progreso` debe invocarse UNA vez por pagina, no solo
    una vez por documento, para que quien llama pueda refrescar la
    interfaz (`QApplication.processEvents()`) con la frecuencia
    suficiente. Ver domain.documents.ports.DocumentExtractor.extract()
    y ui.wizard.etapas.EtapaProcesar._on_procesar()."""
    imagen_pagina1 = raiz / "pagina1.png"
    imagen_pagina2 = raiz / "pagina2.png"
    _imagen_con_texto(imagen_pagina1, "PRIMERA PAGINA")
    _imagen_con_texto(imagen_pagina2, "SEGUNDA PAGINA")

    ruta_pdf = raiz / "escaneado.pdf"
    documento_pdf = fitz.open()
    for imagen in (imagen_pagina1, imagen_pagina2):
        pagina = documento_pdf.new_page()
        rect = pagina.rect
        pagina.insert_image(rect, filename=str(imagen))
    documento_pdf.save(str(ruta_pdf))
    documento_pdf.close()

    llamadas: list[tuple[int, int]] = []
    PdfOcrExtractor(motor_ocr).extract(
        str(ruta_pdf),
        FormatoDocumento.PDF,
        TipoProcesamiento.OCR,
        on_progreso=lambda pagina, total: llamadas.append((pagina, total)),
    )
    assert llamadas == [(1, 2), (2, 2)]


def test_pdf_ocr_extractor_pdf_ilegible_lanza_excepcion(raiz: Path, motor_ocr: TesseractOcrEngine) -> None:
    from domain.documents.exceptions import ExtractionFailedError

    ruta = raiz / "no_es_pdf.pdf"
    ruta.write_bytes(b"esto no es un pdf valido")

    with pytest.raises(ExtractionFailedError):
        PdfOcrExtractor(motor_ocr).extract(str(ruta), FormatoDocumento.PDF, TipoProcesamiento.OCR)
