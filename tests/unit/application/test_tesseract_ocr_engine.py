"""Prueba real de TesseractOcrEngine contra el binario de Tesseract
instalado en este entorno (no un doble de prueba: el proposito de este
adaptador es justamente envolver un proceso externo real). Este entorno
solo tiene instalados los paquetes de idioma 'eng'/'osd' -- no 'spa' --
asi que las pruebas de reconocimiento de texto usan lang='eng', y una
prueba dedicada confirma el mensaje claro de OcrEngineUnavailableError
al pedir 'spa' a solas (sin 'eng' de respaldo).
"""
from __future__ import annotations

import io
import random

import pytesseract
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from domain.documents.exceptions import OcrEngineUnavailableError
from infrastructure.extraction import tesseract_ocr_engine as _motor
from infrastructure.extraction.tesseract_ocr_engine import (
    TesseractOcrEngine,
    _detectar_angulo_inclinacion,
    _preprocesar_para_ocr,
    _umbral_otsu,
    ocr_dependencies_available,
)

_FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _imagen_con_texto(texto: str) -> bytes:
    fuente = ImageFont.truetype(_FUENTE, 40)
    imagen = Image.new("RGB", (600, 100), color="white")
    ImageDraw.Draw(imagen).text((10, 10), texto, font=fuente, fill="black")
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def test_reconoce_texto_real_con_idioma_instalado() -> None:
    engine = TesseractOcrEngine(lang="eng")
    texto, advertencias, rangos = engine.image_to_text(_imagen_con_texto("HELLO WORLD"))
    assert "HELLO WORLD" in texto
    assert advertencias == []
    # Texto nitido y grande, sin razon para que Tesseract dude de el --
    # no deberia haber ningun rango de baja confianza.
    assert rangos == []


def test_imagen_en_blanco_devuelve_cadena_vacia() -> None:
    engine = TesseractOcrEngine(lang="eng")
    imagen_en_blanco = Image.new("RGB", (100, 40), color="white")
    buffer = io.BytesIO()
    imagen_en_blanco.save(buffer, format="PNG")

    texto, advertencias, rangos = engine.image_to_text(buffer.getvalue())
    assert texto == ""
    assert advertencias == []
    assert rangos == []


def test_idioma_solicitado_sin_paquete_instalado_lanza_error_claro() -> None:
    # 'spa' a solas (sin 'eng' de respaldo) -- este entorno no tiene el
    # paquete 'tesseract-ocr-spa' instalado, y a diferencia de un lang
    # combinado ('spa+eng'), aqui NINGUN idioma solicitado carga, que es
    # el caso real en el que Tesseract si falla.
    engine = TesseractOcrEngine(lang="spa")
    with pytest.raises(OcrEngineUnavailableError, match="idioma"):
        engine.image_to_text(_imagen_con_texto("HELLO WORLD"))


def test_bytes_que_no_son_una_imagen_valida_lanzan_error_claro() -> None:
    engine = TesseractOcrEngine(lang="eng")
    with pytest.raises(OcrEngineUnavailableError):
        engine.image_to_text(b"esto no es una imagen valida")


def test_idioma_por_defecto_no_falla_aunque_falte_el_paquete_de_espanol() -> None:
    # Comportamiento real confirmado (ver docstring del modulo): con un
    # lang combinado, Tesseract ignora en silencio el idioma que no
    # tiene paquete instalado mientras al menos uno si lo tenga.
    engine = TesseractOcrEngine()  # lang por defecto: "spa+eng"
    texto, _advertencias, _rangos = engine.image_to_text(_imagen_con_texto("HELLO WORLD"))
    assert "HELLO WORLD" in texto


def test_ocr_dependencies_available_refleja_los_paquetes_reales_instalados() -> None:
    assert ocr_dependencies_available(lang="eng") is True
    assert ocr_dependencies_available(lang="spa") is False
    assert ocr_dependencies_available(lang="spa+eng") is False


def _imagen_con_tabla() -> bytes:
    """Tabla sintetica de 3 columnas x 4 filas (encabezado + 3 filas de
    datos), con huecos horizontales claros entre columnas -- mismo tipo
    de layout que el plan de estudios por cuatrimestre reportado por el
    consultor (2026-07-31) que motivo domain.documents.
    ocr_table_reconstruction."""
    fuente = ImageFont.truetype(_FUENTE, 28)
    imagen = Image.new("RGB", (900, 260), color="white")
    dibujo = ImageDraw.Draw(imagen)
    filas = [
        ["Semester1", "Semester2", "Semester3"],
        ["Calculus", "Statistics", "Physics"],
        ["Algebra", "Electricity", "Economy"],
        ["Ethics", "Research", "Optional"],
    ]
    columnas_x = (20, 320, 620)
    y = 20
    for fila in filas:
        for x, texto in zip(columnas_x, fila, strict=True):
            dibujo.text((x, y), texto, font=fuente, fill="black")
        y += 55
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def test_tabla_escaneada_se_reconstruye_como_tabla_markdown() -> None:
    """Prueba real de punta a punta (bug real reportado 2026-07-31 -- ver
    domain.documents.ocr_table_reconstruction): antes de ese cambio, este
    mismo texto habria salido como un bloque plano con las tres columnas
    concatenadas por fila, sin indicar a cual pertenecia cada materia."""
    engine = TesseractOcrEngine(lang="eng")

    resultado, advertencias, _rangos = engine.image_to_text(_imagen_con_tabla())

    lineas = [linea for linea in resultado.split("\n") if linea.strip()]
    assert len(lineas) == 5  # encabezado + separador + 3 filas de datos
    assert all(linea.count("|") == 4 for linea in lineas)  # 3 columnas -> 4 barras por fila
    assert lineas[1].replace(" ", "") == "|---|---|---|"
    assert "Statistics" in lineas[2]
    assert "Electricity" in lineas[3]
    assert "Optional" in lineas[4]
    assert advertencias == []


# -- Preprocesamiento de imagen + deskew (2026-08-24) --------------------
# Adaptado de RAG STUDIO (escala de grises + ruido + binarizacion Otsu +
# bandas de color) mas deskew (pieza propia de este proyecto) -- ver
# docstring del modulo. Todas las pruebas de esta seccion comparan
# `preprocess=True` (por defecto) contra `preprocess=False` sobre la
# MISMA imagen, para demostrar la mejora real, no solo que el codigo no
# truena.


def _imagen_con_texto_ruidosa_bytes(texto: str, prob_ruido: float = 0.15, seed: int = 42) -> bytes:
    """Agrega ruido de sal y pimienta a una imagen de texto nitido --
    calibrado empiricamente (ver bitacora): con prob_ruido=0.15,
    Tesseract sin preprocesar no reconoce nada de este texto en este
    entorno; con escala de grises + filtro de medianas + Otsu, lo
    reconoce completo."""
    fuente = ImageFont.truetype(_FUENTE, 40)
    imagen = Image.new("RGB", (600, 100), color="white")
    ImageDraw.Draw(imagen).text((10, 10), texto, font=fuente, fill="black")
    aleatorio = random.Random(seed)
    pixeles = imagen.load()
    ancho, alto = imagen.size
    for x in range(ancho):
        for y in range(alto):
            if aleatorio.random() < prob_ruido:
                valor = aleatorio.choice([0, 255])
                pixeles[x, y] = (valor, valor, valor)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def test_preprocesamiento_recupera_texto_de_una_imagen_ruidosa() -> None:
    imagen_ruidosa = _imagen_con_texto_ruidosa_bytes("HELLO WORLD")

    sin_preprocesar = TesseractOcrEngine(lang="eng", preprocess=False)
    con_preprocesar = TesseractOcrEngine(lang="eng", preprocess=True)

    texto_sin, _advertencias, _rangos = sin_preprocesar.image_to_text(imagen_ruidosa)
    texto_con, _advertencias, _rangos = con_preprocesar.image_to_text(imagen_ruidosa)

    assert texto_sin == ""  # sin preprocesar, el ruido rompe el reconocimiento por completo.
    assert texto_con == "HELLO WORLD"  # con preprocesar, se recupera limpio.


def _imagen_multi_linea_rotada_bytes(lineas: list[str], angulo: float, tam: int = 32) -> bytes:
    """Tres lineas de texto nitido, rotadas `angulo` grados -- simula un
    documento escaneado/fotografiado ligeramente torcido."""
    fuente = ImageFont.truetype(_FUENTE, tam)
    imagen = Image.new("RGB", (700, 60 + 50 * len(lineas)), color="white")
    dibujo = ImageDraw.Draw(imagen)
    y = 20
    for linea in lineas:
        dibujo.text((20, y), linea, font=fuente, fill="black")
        y += 50
    rotada = imagen.rotate(angulo, resample=Image.BICUBIC, fillcolor=(255, 255, 255), expand=False)
    buffer = io.BytesIO()
    rotada.save(buffer, format="PNG")
    return buffer.getvalue()


def test_deskew_recupera_texto_de_una_imagen_inclinada() -> None:
    # Calibrado empiricamente (ver bitacora): a 5 grados de inclinacion,
    # Tesseract sin preprocesar reordena y corta mal las lineas; con
    # deskew, las reconoce en el orden y contenido correctos.
    lineas = [
        "This is the first line of text.",
        "Here comes a second line as well.",
        "And finally a third line too.",
    ]
    imagen_inclinada = _imagen_multi_linea_rotada_bytes(lineas, angulo=5)

    sin_preprocesar = TesseractOcrEngine(lang="eng", preprocess=False)
    con_preprocesar = TesseractOcrEngine(lang="eng", preprocess=True)

    texto_sin, _advertencias, _rangos = sin_preprocesar.image_to_text(imagen_inclinada)
    texto_con, _advertencias, _rangos = con_preprocesar.image_to_text(imagen_inclinada)

    assert not all(linea in texto_sin for linea in lineas)  # sin deskew, algo se pierde o desordena.
    for linea in lineas:
        assert linea in texto_con  # con deskew, las tres lineas se reconocen completas.


def test_detectar_angulo_inclinacion_encuentra_el_angulo_correctivo() -> None:
    """Prueba directa de la funcion de deteccion (no de punta a punta):
    inyecta una inclinacion conocida y confirma que el angulo detectado
    es el que la corrige -- mismo criterio de signo que `Image.rotate`
    (rotar la imagen ese mismo angulo la endereza), sin ninguna
    conversion de signo adicional en el codigo de produccion."""
    fuente = ImageFont.truetype(_FUENTE, 32)
    imagen = Image.new("RGB", (700, 160), color="white")
    ImageDraw.Draw(imagen).text((20, 20), "Texto de prueba para deskew.", font=fuente, fill="black")

    for angulo_inyectado in (5.0, -3.0):
        rotada = imagen.rotate(angulo_inyectado, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
        gris = rotada.convert("L")
        sin_ruido = gris.filter(ImageFilter.MedianFilter(size=3))
        umbral = _umbral_otsu(sin_ruido.histogram())
        binaria = sin_ruido.point(lambda p, umbral=umbral: 255 if p > umbral else 0)

        angulo_detectado = _detectar_angulo_inclinacion(binaria)

        assert abs(angulo_detectado - (-angulo_inyectado)) <= 1.0


def test_detectar_angulo_inclinacion_no_rota_una_imagen_ya_derecha() -> None:
    fuente = ImageFont.truetype(_FUENTE, 32)
    imagen = Image.new("RGB", (700, 160), color="white")
    ImageDraw.Draw(imagen).text((20, 20), "Texto de prueba ya derecho.", font=fuente, fill="black")
    binaria = imagen.convert("L").point(lambda p: 255 if p > 128 else 0)

    assert _detectar_angulo_inclinacion(binaria) == 0.0


def _imagen_con_banda_de_color_bytes() -> bytes:
    """Encabezado de seccion con fondo de color saturado y texto blanco
    encima -- mismo tipo de layout que motivo la recuperacion de bandas
    de color en RAG STUDIO (Ronda 22: un encabezado de cuatrimestre
    sobre fondo turquesa que Tesseract omitia por completo)."""
    fuente_banda = ImageFont.truetype(_FUENTE, 24)
    fuente_cuerpo = ImageFont.truetype(_FUENTE, 28)
    imagen = Image.new("RGB", (700, 200), color="white")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rectangle([(0, 20), (700, 55)], fill=(0, 180, 180))
    dibujo.text((15, 26), "1ER CUATRIMESTRE", font=fuente_banda, fill="white")
    dibujo.text((15, 110), "Normal body text below the header band.", font=fuente_cuerpo, fill="black")
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def test_banda_de_color_se_recupera_y_se_marca_como_baja_confianza() -> None:
    """No reproduce exactamente el bug original de RAG STUDIO (el
    reconocimiento de la pagina completa, en este entorno y con esta
    imagen sintetica, si degrada el texto de la banda al binarizarla --
    ver bitacora), pero confirma que el MECANISMO de recuperacion
    funciona de punta a punta: se detecta la banda, se recorta y
    reconoce aparte, el texto recuperado se agrega al final marcado con
    un encabezado explicito, se registra una advertencia, y cada linea
    recuperada queda como RangoBajaConfianza (confianza 0.0 a proposito
    -- ver su constante -- para que la interfaz la resalte igual que
    cualquier otro tramo de baja confianza, Nivel 1)."""
    engine = TesseractOcrEngine(lang="eng")

    texto, advertencias, rangos = engine.image_to_text(_imagen_con_banda_de_color_bytes())

    assert "[Texto adicional recuperado de bandas de color" in texto
    assert len(advertencias) == 1
    assert "banda" in advertencias[0].lower()

    rangos_de_banda = [r for r in rangos if r.confianza == 0.0]
    assert len(rangos_de_banda) >= 1
    for rango in rangos_de_banda:
        # Bookkeeping de posicion correcto: el tramo señalado coincide
        # exactamente con el texto que dice haber marcado.
        assert texto[rango.inicio : rango.fin] == rango.texto


def test_preprocesamiento_no_empeora_una_imagen_ya_nitida() -> None:
    # Regresion: el preprocesamiento (activado por defecto) no debe
    # perjudicar el caso ya cubierto por
    # test_reconoce_texto_real_con_idioma_instalado -- se repite aqui
    # de forma explicita para dejar constancia de la comparacion
    # sin/con, no solo confiar en que la otra prueba siga en verde.
    imagen = _imagen_con_texto("HELLO WORLD")
    sin_preprocesar = TesseractOcrEngine(lang="eng", preprocess=False)
    con_preprocesar = TesseractOcrEngine(lang="eng", preprocess=True)

    texto_sin, _, _ = sin_preprocesar.image_to_text(imagen)
    texto_con, _, _ = con_preprocesar.image_to_text(imagen)

    assert texto_sin == "HELLO WORLD"
    assert texto_con == "HELLO WORLD"


def test_preprocesar_para_ocr_devuelve_una_imagen_nueva_sin_modificar_la_original() -> None:
    imagen = _imagen_con_texto("HELLO WORLD")
    original = Image.open(io.BytesIO(imagen))
    copia_para_comparar = original.copy()

    resultado = _preprocesar_para_ocr(original)

    assert resultado is not original
    assert list(original.getdata()) == list(copia_para_comparar.getdata())


# -- Correcciones de la auditoria 2026-08-24 ------------------------------
# Cuatro hallazgos reales de una auditoria profunda posterior a la ronda
# de arriba, todos confirmados empiricamente contra el codigo real antes
# de escribir la asercion (mismo criterio del resto de este archivo).


def test_imagen_truncada_lanza_error_claro_en_vez_de_reventar() -> None:
    """Bug real: Image.open() decodifica de forma perezosa, asi que una
    imagen truncada (encabezado PNG valido, datos incompletos -- un
    archivo cortado a la mitad, plausible ante una copia interrumpida)
    NO fallaba ahi, sino recien dentro de _preprocesar_para_ocr(), fuera
    de cualquier try/except, con un OSError crudo sin capturar. Confirmado
    empiricamente: truncar los bytes de un PNG valido a la mitad pasa
    Image.open() sin error y solo falla al forzar la decodificacion."""
    engine = TesseractOcrEngine(lang="eng")
    imagen_completa = _imagen_con_texto("HELLO WORLD")
    imagen_truncada = imagen_completa[: len(imagen_completa) // 2]

    with pytest.raises(OcrEngineUnavailableError):
        engine.image_to_text(imagen_truncada)


def test_muchas_bandas_de_color_descartan_la_recuperacion_de_la_pagina_completa() -> None:
    """Bug real: _MAX_BANDAS_COLOR_POR_PAGINA decia en su docstring que
    una pagina con mas de 10 bandas "plausibles" (tipicamente una
    fotografia o una plantilla con franjas de color, no un documento con
    encabezados de seccion reales) se descarta por completo -- pero el
    codigo hacia `bandas_plausibles[:10]`, truncando en vez de descartar,
    y seguia disparando hasta 10 reconocimientos OCR de bajo valor.
    Confirmado empiricamente: una imagen con mas de 10 franjas de color
    horizontales (simulando ese caso) no debe producir ningun texto
    recuperado."""
    imagen = Image.new("RGB", (700, 400), color="white")
    dibujo = ImageDraw.Draw(imagen)
    colores = [(0, 180, 180), (180, 0, 180), (180, 180, 0), (0, 120, 220)]
    y = 0
    i = 0
    while y + 15 < 400:
        dibujo.rectangle([(0, y), (700, y + 15)], fill=colores[i % len(colores)])
        y += 30
        i += 1
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")

    engine = TesseractOcrEngine(lang="eng")
    texto, advertencias, rangos = engine.image_to_text(buffer.getvalue())

    assert "[Texto adicional recuperado de bandas de color" not in texto
    assert advertencias == []
    assert rangos == []


def _sin_palabras_reconocidas(*_args: object, **_kwargs: object) -> dict[str, list[object]]:
    """Reemplazo de pytesseract.image_to_data() que simula una pagina sin
    NINGUNA palabra de cuerpo reconocible -- mismo formato de diccionario
    que devuelve la funcion real, pero todas las listas vacias."""
    return {
        "text": [],
        "conf": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
    }


def test_texto_recuperado_de_banda_sin_cuerpo_no_tiene_espacio_en_blanco_al_inicio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bug real: si la pagina no produce NINGUNA palabra de cuerpo
    (texto_reconstruido vacio) pero si se recupera texto de una banda de
    color, el texto devuelto empezaba con "\\n\\n[Texto adicional...".
    PdfOcrExtractor/ImageOcrExtractor le aplican ademas su propio
    `.strip()` defensivo antes de guardarlo, lo que corria las
    posiciones reales pero dejaba los RangoBajaConfianza ya calculados
    apuntando a los caracteres equivocados. Se fuerza aqui el caso "sin
    ninguna palabra de cuerpo" con un reemplazo de
    pytesseract.image_to_data(), y se confirma que el texto devuelto por
    image_to_text() en si mismo YA no tiene espacio en blanco al inicio
    (ver el fix: recorte final con reajuste de rangos), asi que cualquier
    `.strip()` adicional de quien llama es un no-op seguro."""
    monkeypatch.setattr(pytesseract, "image_to_data", _sin_palabras_reconocidas)
    engine = TesseractOcrEngine(lang="eng")

    texto, advertencias, rangos = engine.image_to_text(_imagen_con_banda_de_color_bytes())

    assert texto == texto.strip()  # nunca queda espacio en blanco al inicio/final.
    assert texto.startswith("[Texto adicional recuperado de bandas de color")
    assert len(advertencias) == 1
    assert len(rangos) >= 1
    for rango in rangos:
        assert texto[rango.inicio : rango.fin] == rango.texto


def test_fallo_al_detectar_bandas_de_color_se_reporta_como_advertencia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bug real: _detectar_bandas_de_color es una funcion pura de PIL sin
    E/S -- cualquier excepcion que produjera se capturaba con
    `except Exception: return []` sin dejar ningun rastro, escondiendo
    para siempre una futura regresion de programacion (a diferencia de un
    fallo puntual de Tesseract en UNA banda, que si es un fallo externo
    esperable y sigue sin reportarse, por diseño). Ahora se reporta como
    advertencia, sin afectar el resultado principal."""
    monkeypatch.setattr(_motor, "_detectar_bandas_de_color", lambda _imagen: (_ for _ in ()).throw(ValueError("bug simulado")))
    engine = TesseractOcrEngine(lang="eng")

    texto, advertencias, _rangos = engine.image_to_text(_imagen_con_texto("HELLO WORLD"))

    assert texto == "HELLO WORLD"  # el resultado principal no se ve afectado.
    assert any("bandas de color" in adv and "bug simulado" in adv for adv in advertencias)
