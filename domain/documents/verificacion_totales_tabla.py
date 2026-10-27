"""Modulo 8 (Nivel 2 de validaciones numericas), 2026-08-01, a pedido
explicito del consultor tras analizar la fatiga visual del revisor al
cotejar volumenes altos de documentos contra el original (ver bitacora):
ademas de la deteccion/validacion de fechas de
`verificacion_fechas_cifras.py`, esta pieza valida que la fila de
"Total" (o "Totales"/"Suma"/"Gran total") de una tabla Markdown
coincida con la suma de las demas filas de datos en cada columna
numerica.

Una discrepancia asi es un hecho aritmetico objetivo (2 + 2 no es 5),
no una opinion sobre si el contenido del documento es correcto: no
rompe el principio de "la herramienta no inventa un veredicto" que
documenta `verificacion_fechas_cifras.py`, porque esta pieza nunca
juzga si una cifra es la CORRECTA para el contrato -- solo si la tabla,
tal como quedo en el Markdown, es aritmeticamente consistente consigo
misma. Si no lo es, puede deberse a un error de OCR/transcripcion (lo
que le interesa a este modulo) o a un error real del documento
original (algo que el revisor debe confirmar contra el original, igual
que con cualquier otro hallazgo de este Modulo 8) -- esta pieza no
distingue entre ambos casos, solo senala la inconsistencia.

Funcion pura, sin dependencias de infrastructure: mismo principio que
`verificacion_fechas_cifras.py` y
`ocr_table_reconstruction.reconstruir_texto_ocr()`.

Limitaciones conocidas, documentadas a proposito (nunca escondidas):
- Solo se valida una fila de "totales" por tabla, identificada por el
  nombre de su primera celda no vacia (comparacion insensible a
  mayusculas: "total", "totales", "suma", "gran total"). Una tabla sin
  ninguna fila asi nombrada no se valida -- no hay forma de adivinar
  cual fila es el total sin esa senal textual.
- Cada columna se valida de forma INDEPENDIENTE: si una fila tiene una
  celda no numerica en una columna (texto, vacia), esa celda se ignora
  al sumar esa columna, pero las demas columnas numericas de la misma
  tabla se siguen validando con normalidad.
- El separador decimal/de miles es ambiguo en texto libre ("1.234"
  podria ser mil doscientos treinta y cuatro, o uno con tres
  decimales) -- ver `_parsear_numero_ambiguo()` para la heuristica
  exacta que resuelve esta ambiguedad.
- Igual que `Documento.mapa_paginas`/`RangoBajaConfianza`, la posicion
  reportada es un desplazamiento en el Markdown analizado (inicio de la
  fila de totales), no una coordenada del documento original.
"""
from __future__ import annotations

import re

from .verificacion_fechas_cifras import HallazgoVerificacion, TipoHallazgoVerificacion

_PATRON_SEPARADOR_CELDA = re.compile(r"(?<!\\)\|")
_PATRON_SOLO_SEPARADORES = re.compile(r"^:?-+:?$")
_PALABRAS_CLAVE_TOTAL = ("total", "totales", "suma", "gran total")
_PATRONES_PALABRA_TOTAL = [re.compile(rf"\b{re.escape(palabra)}\b") for palabra in _PALABRAS_CLAVE_TOTAL]
"""Patrones de PALABRA COMPLETA (no subcadena) para cada clave de
`_PALABRAS_CLAVE_TOTAL` -- auditoria 2026-08-24: un simple `palabra in
texto` hacia que "Subtotal" (subcadena que contiene "total") se
confundiera con la fila de total real, tomando la primera fila que
matcheaba (`next(...)` en `_verificar_tabla`) en vez de la fila de
"Total"/"Gran total" que de verdad cierra la tabla -- un falso positivo
activo justo en el escenario mas comun de tablas contables (subtotal
intermedio + total final). Con limite de palabra, "Subtotal" ya no
activa ninguno de los patrones."""
_TOLERANCIA = 0.01
"""Diferencia maxima (en la misma unidad que las cifras de la tabla,
tipicamente moneda) entre la suma calculada y el total declarado antes
de considerarse una discrepancia real -- no cero, para tolerar el
redondeo normal de centavos al sumar varios valores en punto
flotante."""


def _es_fila_tabla(linea: str) -> bool:
    """Una fila de tabla Markdown empieza y termina con '|' y tiene al
    menos dos de ellos (una sola columna con celdas vacias a los lados
    no cuenta como tabla) -- mismo formato que emite
    `ocr_table_reconstruction._fila_markdown()`."""
    fragmento = linea.strip()
    return fragmento.startswith("|") and fragmento.endswith("|") and fragmento.count("|") >= 2


def _celdas(linea: str) -> list[str]:
    """Divide una fila de tabla en sus celdas, respetando '|' escapados
    ('\\|', ver `ocr_table_reconstruction._escapar_celda()`) y
    descartando los tramos vacios antes del primer separador y despues
    del ultimo."""
    partes = _PATRON_SEPARADOR_CELDA.split(linea.strip())
    interior = partes[1:-1] if len(partes) >= 2 else []
    return [celda.strip().replace("\\|", "|") for celda in interior]


def _es_fila_separadora(linea: str) -> bool:
    """La fila de guiones ('| --- | --- |', con o sin ':' de
    alineacion) que Markdown exige justo despues del encabezado de una
    tabla."""
    celdas = _celdas(linea)
    return bool(celdas) and all(_PATRON_SOLO_SEPARADORES.match(celda.replace(" ", "")) for celda in celdas)


def _fila_es_total(celdas: list[str]) -> bool:
    """True si la primera celda no vacia de la fila contiene, como
    PALABRA COMPLETA, alguna de las claves de `_PALABRAS_CLAVE_TOTAL`
    (insensible a mayusculas) -- la unica senal disponible para
    identificar cual fila es el total, ver docstring del modulo. Se
    compara por palabra completa (no subcadena) para no confundir
    "Subtotal" con "Total" (auditoria 2026-08-24, ver
    `_PATRONES_PALABRA_TOTAL`)."""
    for celda in celdas:
        texto = celda.strip().lower()
        if texto:
            return any(patron.search(texto) for patron in _PATRONES_PALABRA_TOTAL)
    return False


def _parsear_numero_ambiguo(texto: str) -> float | None:
    """Interpreta `texto` como numero, resolviendo la ambiguedad real
    entre separador decimal y de miles cuando el texto usa ',' y/o '.':

    - Si aparecen AMBOS ('1.234,56' o '1,234.56'): el que aparece MAS A
      LA DERECHA es el separador decimal (asi funcionan ambas
      convenciones reales, latina e inglesa) -- el otro se descarta
      como separador de miles.
    - Si aparece solo UNO de los dos, mas de una vez ('1.234.567'), es
      separador de miles (un numero solo puede tener un separador
      decimal).
    - Si aparece solo UNO de los dos, una sola vez, se decide por la
      cantidad de digitos que le siguen: EXACTAMENTE 3 ('1.234') se
      interpreta como separador de miles (agrupacion de miles
      estandar); cualquier otra cantidad ('1.5', '1.25') se interpreta
      como separador decimal.

    Tolera un signo '$'/'€'/'%'/espacio al inicio o final, y parentesis
    o '-' como negativo (convencion contable). Devuelve `None` si
    `texto` no queda como un numero valido tras limpiarlo (por ejemplo,
    la celda con la propia etiqueta "Total")."""
    limpio = texto.strip()
    if not limpio:
        return None
    negativo = False
    if limpio.startswith("(") and limpio.endswith(")"):
        negativo = True
        limpio = limpio[1:-1].strip()
    limpio = limpio.strip("$€ %\t")
    if limpio.startswith("-"):
        negativo = True
        limpio = limpio[1:]
    if not limpio or not re.fullmatch(r"\d[\d.,]*\d|\d", limpio):
        return None

    tiene_coma = "," in limpio
    tiene_punto = "." in limpio
    if tiene_coma and tiene_punto:
        separador_decimal = "," if limpio.rfind(",") > limpio.rfind(".") else "."
        separador_miles = "," if separador_decimal == "." else "."
        limpio = limpio.replace(separador_miles, "").replace(separador_decimal, ".")
    elif tiene_coma or tiene_punto:
        separador = "," if tiene_coma else "."
        digitos_despues_del_ultimo = limpio[limpio.rfind(separador) + 1 :]
        es_miles = limpio.count(separador) > 1 or len(digitos_despues_del_ultimo) == 3
        limpio = limpio.replace(separador, "") if es_miles else limpio.replace(separador, ".")

    try:
        valor = float(limpio)
    except ValueError:
        return None
    return -valor if negativo else valor


def _verificar_tabla(
    filas_datos: list[tuple[int, list[str]]], num_columnas: int, offsets: list[int]
) -> list[HallazgoVerificacion]:
    indice_total = next((i for i, (_, celdas) in enumerate(filas_datos) if _fila_es_total(celdas)), None)
    if indice_total is None:
        return []
    numero_linea_total, celdas_total = filas_datos[indice_total]
    filas_sumables = [celdas for i, (_, celdas) in enumerate(filas_datos) if i != indice_total]
    if not filas_sumables:
        return []

    hallazgos: list[HallazgoVerificacion] = []
    for columna in range(num_columnas):
        if columna >= len(celdas_total):
            continue
        valor_total = _parsear_numero_ambiguo(celdas_total[columna])
        if valor_total is None:
            continue  # celda no numerica en esta columna -- probablemente la etiqueta "Total".
        suma = 0.0
        alguna_celda_sumada = False
        for celdas in filas_sumables:
            if columna >= len(celdas):
                continue
            valor = _parsear_numero_ambiguo(celdas[columna])
            if valor is None:
                continue
            suma += valor
            alguna_celda_sumada = True
        if not alguna_celda_sumada or abs(suma - valor_total) <= _TOLERANCIA:
            continue
        hallazgos.append(
            HallazgoVerificacion(
                tipo=TipoHallazgoVerificacion.CIFRA,
                texto=celdas_total[columna],
                posicion=offsets[numero_linea_total],
                advertencia=(
                    f"La columna {columna + 1} de esta tabla suma {suma:g}, pero la fila de "
                    f"total dice {valor_total:g} -- revisar contra el original."
                ),
            )
        )
    return hallazgos


def verificar_totales_de_tablas(markdown: str) -> list[HallazgoVerificacion]:
    """Recorre `markdown` buscando tablas (encabezado + fila separadora
    + filas de datos, formato estandar que ya emite
    `ocr_table_reconstruction.reconstruir_texto_ocr()` o cualquier
    convertidor de DOCX/XLSX a Markdown de este proyecto) y devuelve un
    `HallazgoVerificacion` por cada columna cuya fila de "Total" no
    coincide con la suma de las demas filas -- ver docstring del modulo
    para la heuristica y sus limitaciones."""
    lineas = markdown.split("\n")
    offsets: list[int] = []
    cursor = 0
    for linea in lineas:
        offsets.append(cursor)
        cursor += len(linea) + 1  # +1 por el '\n' que separa() ya quito.

    hallazgos: list[HallazgoVerificacion] = []
    i = 0
    n = len(lineas)
    while i < n:
        if _es_fila_tabla(lineas[i]) and i + 1 < n and _es_fila_separadora(lineas[i + 1]):
            num_columnas = len(_celdas(lineas[i]))
            fin = i + 2
            filas_datos: list[tuple[int, list[str]]] = []
            while fin < n and _es_fila_tabla(lineas[fin]):
                filas_datos.append((fin, _celdas(lineas[fin])))
                fin += 1
            hallazgos.extend(_verificar_tabla(filas_datos, num_columnas, offsets))
            i = fin
        else:
            i += 1
    return hallazgos
