"""Pruebas de domain.documents.ocr_table_reconstruction -- funcion pura,
sin pytesseract (ver tests/unit/application/test_tesseract_ocr_engine.py
para la prueba de punta a punta contra el binario real de Tesseract, con
una imagen sintetica de tabla)."""
from __future__ import annotations

from domain.documents.ocr_table_reconstruction import UMBRAL_CONFIANZA_BAJA, PalabraOcr, reconstruir_texto_ocr


def _palabra(
    texto: str,
    izquierda: int,
    linea_id: tuple[int, int, int],
    alto: int = 30,
    ancho: int = 80,
    confianza: float = 100.0,
) -> PalabraOcr:
    return PalabraOcr(
        texto=texto, izquierda=izquierda, arriba=0, ancho=ancho, alto=alto, linea_id=linea_id, confianza=confianza
    )


def test_tres_o_mas_lineas_con_el_mismo_numero_de_columnas_se_reconstruyen_como_tabla() -> None:
    palabras = [
        _palabra("Cuatrimestre1", 0, (1, 1, 1)),
        _palabra("Cuatrimestre2", 300, (1, 1, 1)),
        _palabra("Cuatrimestre3", 600, (1, 1, 1)),
        _palabra("Calculo", 0, (1, 1, 2)),
        _palabra("Estadistica", 300, (1, 1, 2)),
        _palabra("Fisica", 600, (1, 1, 2)),
        _palabra("Algebra", 0, (1, 1, 3)),
        _palabra("Electricidad", 300, (1, 1, 3)),
        _palabra("Economia", 600, (1, 1, 3)),
    ]

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    lineas = resultado.split("\n")
    assert lineas[0] == "| Cuatrimestre1 | Cuatrimestre2 | Cuatrimestre3 |"
    assert lineas[1] == "| --- | --- | --- |"
    assert lineas[2] == "| Calculo | Estadistica | Fisica |"
    assert lineas[3] == "| Algebra | Electricidad | Economia |"
    assert advertencias == []


def test_solo_dos_lineas_con_columnas_no_alcanza_el_minimo_y_no_se_trata_como_tabla() -> None:
    # _MIN_FILAS_TABLA exige al menos 3 lineas consecutivas -- dos lineas
    # con "huecos grandes" pueden ser una coincidencia (por ejemplo, dos
    # encabezados sueltos), no necesariamente una tabla real.
    palabras = [
        _palabra("Titulo", 0, (1, 1, 1)),
        _palabra("Subtitulo", 400, (1, 1, 1)),
        _palabra("Autor", 0, (1, 1, 2)),
        _palabra("Fecha", 400, (1, 1, 2)),
    ]

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    assert "|" not in resultado
    assert "Titulo Subtitulo" in resultado
    assert "Autor Fecha" in resultado
    assert advertencias == []


def test_parrafo_normal_no_se_confunde_con_tabla() -> None:
    # Palabras de una misma frase, separadas por huecos normales (mucho
    # menores a _UMBRAL_CLUSTER_COLUMNA * altura) -- deben quedar en una
    # sola columna por linea, nunca partirse en columnas falsas.
    palabras = [
        _palabra("Este", 0, (1, 1, 1)),
        _palabra("es", 90, (1, 1, 1)),
        _palabra("un", 130, (1, 1, 1)),
        _palabra("parrafo", 170, (1, 1, 1)),
        _palabra("normal", 90, (1, 1, 2)),  # nueva linea, mismo bloque/parrafo
    ]

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    assert "|" not in resultado
    assert resultado == "Este es un parrafo\nnormal"
    assert advertencias == []


def test_cambio_de_parrafo_agrega_linea_en_blanco() -> None:
    palabras = [
        _palabra("Primer", 0, (1, 1, 1)),
        _palabra("parrafo.", 90, (1, 1, 1)),
        _palabra("Segundo", 0, (1, 2, 1)),
        _palabra("parrafo.", 100, (1, 2, 1)),
    ]

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    assert resultado == "Primer parrafo.\n\nSegundo parrafo."
    assert advertencias == []


def test_celda_con_barra_vertical_se_escapa_para_no_romper_la_tabla() -> None:
    palabras = [
        _palabra("A|B", 0, (1, 1, 1)),
        _palabra("C", 300, (1, 1, 1)),
        _palabra("D", 600, (1, 1, 1)),
        _palabra("E", 0, (1, 1, 2)),
        _palabra("F", 300, (1, 1, 2)),
        _palabra("G", 600, (1, 1, 2)),
        _palabra("H", 0, (1, 1, 3)),
        _palabra("I", 300, (1, 1, 3)),
        _palabra("J", 600, (1, 1, 3)),
    ]

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    assert "| A\\|B | C | D |" in resultado
    assert advertencias == []


def test_sin_palabras_devuelve_cadena_vacia() -> None:
    assert reconstruir_texto_ocr([]) == ("", [], [])


def test_fila_incompleta_justo_despues_de_una_tabla_se_senala_como_advertencia() -> None:
    """Caso real confirmado 2026-07-31 (PROY-6955_udl_3, plan de estudios
    escaneado): la sexta fila de una tabla de 3 columnas
    ('Metodologia de la Investigacion' / 'Economia' / 'Autoconocimiento')
    llega en 3 lineas/bloques de Tesseract distintos -- una por columna --
    en vez de una sola linea con 3 columnas. No se puede reconstruir con
    seguridad (ver la limitacion documentada en el modulo), asi que debe
    senalarse como advertencia sin alterar el texto de salida."""
    palabras = [
        _palabra("Cuatrimestre1", 0, (1, 1, 1)),
        _palabra("Cuatrimestre2", 300, (1, 1, 1)),
        _palabra("Cuatrimestre3", 600, (1, 1, 1)),
        _palabra("Calculo", 0, (1, 1, 2)),
        _palabra("Estadistica", 300, (1, 1, 2)),
        _palabra("Fisica", 600, (1, 1, 2)),
        _palabra("Algebra", 0, (1, 1, 3)),
        _palabra("Electricidad", 300, (1, 1, 3)),
        _palabra("Economia", 600, (1, 1, 3)),
        # Fila incompleta: cada "columna" llega en su propia linea/bloque.
        _palabra("Metodologia", 0, (1, 2, 1)),
        _palabra("Economia2", 0, (1, 2, 2)),
        _palabra("Autoconocimiento", 0, (2, 1, 1)),
    ]

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    # El texto de salida no cambia: las 3 lineas sueltas se emiten igual
    # que cualquier otro texto no reconocido como tabla.
    assert "Metodologia" in resultado
    assert "Economia2" in resultado
    assert "Autoconocimiento" in resultado
    assert len(advertencias) == 1
    assert "fila de tabla incompleta" in advertencias[0]
    assert "Metodologia" in advertencias[0]
    assert "Economia2" in advertencias[0]
    assert "Autoconocimiento" in advertencias[0]


def test_parrafo_normal_despues_de_tabla_no_se_marca_como_fila_incompleta() -> None:
    """Un parrafo largo (mas de _MAX_PALABRAS_FRAGMENTO_COLA palabras) no
    debe confundirse con un fragmento de fila -- la mayoria del texto
    plano tiene una sola columna, asi que sin este limite CUALQUIER
    parrafo despues de una tabla se marcaria como advertencia."""
    palabras = [
        _palabra("Cuatrimestre1", 0, (1, 1, 1)),
        _palabra("Cuatrimestre2", 300, (1, 1, 1)),
        _palabra("Cuatrimestre3", 600, (1, 1, 1)),
        _palabra("Calculo", 0, (1, 1, 2)),
        _palabra("Estadistica", 300, (1, 1, 2)),
        _palabra("Fisica", 600, (1, 1, 2)),
        _palabra("Algebra", 0, (1, 1, 3)),
        _palabra("Electricidad", 300, (1, 1, 3)),
        _palabra("Economia", 600, (1, 1, 3)),
    ]
    parrafo_largo = (
        "Este es un parrafo normal de mas de ocho palabras que no deberia "
        "confundirse jamas con un fragmento de una fila de tabla"
    ).split()
    izquierda = 0
    for palabra in parrafo_largo:
        palabras.append(_palabra(palabra, izquierda, (1, 2, 1)))
        izquierda += 90

    resultado, advertencias, _rangos = reconstruir_texto_ocr(palabras)

    assert "Este es un parrafo normal" in resultado
    assert advertencias == []


def test_palabra_de_confianza_normal_no_genera_ningun_rango() -> None:
    palabras = [
        _palabra("Este", 0, (1, 1, 1), confianza=95.0),
        _palabra("parrafo", 90, (1, 1, 1), confianza=80.0),
    ]

    _resultado, _advertencias, rangos = reconstruir_texto_ocr(palabras)

    assert rangos == []


def test_palabra_de_baja_confianza_se_localiza_en_el_texto_reconstruido() -> None:
    palabras = [
        _palabra("Este", 0, (1, 1, 1), confianza=95.0),
        _palabra("es", 90, (1, 1, 1), confianza=95.0),
        _palabra("dud0so", 130, (1, 1, 1), confianza=35.0),
    ]

    resultado, _advertencias, rangos = reconstruir_texto_ocr(palabras)

    assert resultado == "Este es dud0so"
    assert len(rangos) == 1
    rango = rangos[0]
    assert rango.texto == "dud0so"
    assert rango.confianza == 35.0
    assert resultado[rango.inicio : rango.fin] == "dud0so"


def test_palabra_justo_en_el_umbral_no_se_marca_como_baja_confianza() -> None:
    # UMBRAL_CONFIANZA_BAJA es el limite: solo estrictamente por debajo
    # cuenta como baja confianza (>= se considera aceptable).
    palabras = [_palabra("normal", 0, (1, 1, 1), confianza=UMBRAL_CONFIANZA_BAJA)]

    _resultado, _advertencias, rangos = reconstruir_texto_ocr(palabras)

    assert rangos == []


def test_varias_palabras_de_baja_confianza_se_localizan_en_orden() -> None:
    palabras = [
        _palabra("aaa1", 0, (1, 1, 1), confianza=20.0),
        _palabra("normal", 200, (1, 1, 1), confianza=95.0),
        _palabra("bbb2", 400, (1, 1, 1), confianza=40.0),
    ]

    resultado, _advertencias, rangos = reconstruir_texto_ocr(palabras)

    assert resultado == "aaa1 normal bbb2"
    assert [r.texto for r in rangos] == ["aaa1", "bbb2"]
    assert resultado[rangos[0].inicio : rangos[0].fin] == "aaa1"
    assert resultado[rangos[1].inicio : rangos[1].fin] == "bbb2"


def test_celda_de_tabla_con_barra_vertical_y_baja_confianza_se_localiza_escapada() -> None:
    palabras = [
        _palabra("A|B", 0, (1, 1, 1), confianza=30.0),
        _palabra("C", 300, (1, 1, 1)),
        _palabra("D", 600, (1, 1, 1)),
        _palabra("E", 0, (1, 1, 2)),
        _palabra("F", 300, (1, 1, 2)),
        _palabra("G", 600, (1, 1, 2)),
        _palabra("H", 0, (1, 1, 3)),
        _palabra("I", 300, (1, 1, 3)),
        _palabra("J", 600, (1, 1, 3)),
    ]

    resultado, _advertencias, rangos = reconstruir_texto_ocr(palabras)

    assert len(rangos) == 1
    rango = rangos[0]
    # La celda quedo escapada ("A\|B") dentro de la tabla Markdown -- el
    # rango debe apuntar a esa version, no a la original sin escapar.
    assert resultado[rango.inicio : rango.fin] == "A\\|B"
