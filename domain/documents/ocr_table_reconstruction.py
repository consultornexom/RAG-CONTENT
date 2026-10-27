"""Modulo 6 (OCR): reconstruccion de tablas a partir de las posiciones de
palabra que Tesseract ya calcula (Documento Maestro, seccion 8.1: "tablas"
es una de las validaciones minimas del dominio "Extraccion", junto con
"orden").

Bug real reportado 2026-07-31 (consultor, con una captura de un plan de
estudios escaneado, organizado por cuatrimestre en columnas): antes de
este modulo, `TesseractOcrEngine` solo llamaba a `image_to_string()`, que
devuelve el texto de la pagina completa como un bloque plano sin ninguna
nocion de columnas -- una tabla de tres columnas (1er/2do/3er
cuatrimestre) terminaba con las materias de las tres columnas
concatenadas en el mismo renglon del Markdown, sin indicar a cual
cuatrimestre pertenecia cada una. El usuario tenia que reconstruir la
tabla a mano en "Revision" para cada documento asi.

Esta funcion es pura y no importa pytesseract (ADR-001, seccion 4: domain
no depende de infrastructure): recibe una lista de `PalabraOcr` (ya
extraida por `infrastructure.extraction.tesseract_ocr_engine` desde
`pytesseract.image_to_data()`) y devuelve el texto reconstruido, con
tablas detectadas emitidas como filas Markdown ('| ... |') en vez de texto
plano -- para que el Modulo 9 (regla `normalizar_espacios_en_tablas`) y el
resto del pipeline las traten igual que una tabla nativa de un DOCX/XLSX.

Heuristica (deteccion aproximada, no perfecta -- limitaciones al final):
dentro de cada linea (agrupada por el trio bloque/parrafo/linea que
Tesseract ya calcula), se agrupan las palabras en "columnas" cuando el
hueco horizontal entre una palabra y la siguiente es mucho mayor que el
hueco normal entre palabras de una misma frase (`_UMBRAL_CLUSTER_COLUMNA`,
proporcional a la altura de la linea, no a un valor fijo de pixeles, para
no depender del DPI de rasterizacion ni del tamano de fuente del
documento). Un grupo de al menos `_MIN_FILAS_TABLA` lineas consecutivas
con el MISMO numero de columnas (2 o mas) se trata como una tabla: la
primera de esas lineas se usa como encabezado, el resto como filas de
datos, emparejando columnas por posicion (columna N de una fila con
columna N de la siguiente) -- valido porque solo se activa cuando el
conteo de columnas ya coincide entre todas las lineas del bloque.

Limitaciones conocidas (documentadas a proposito, no escondidas):
- Tablas con celdas vacias en algunas filas (numero de columnas
  inconsistente entre filas) no se detectan como tabla y se tratan como
  texto normal.
- Tablas sin un hueco claro entre columnas (texto muy apretado) tampoco
  se detectan.
- El emparejamiento posicional de columnas puede fallar si una fila tiene
  sus palabras agrupadas de forma distinta a las demas del mismo bloque
  (por ejemplo, una celda vacia en medio de la fila que hace que las
  columnas siguientes "se recorran").
- En todos estos casos el resultado es el mismo texto plano que se
  obtenia antes de este cambio -- nunca peor que antes, solo
  potencialmente sin la mejora.

Limitacion adicional confirmada 2026-07-31 (analisis de una corrida real,
PROY-6955_udl_3, mismo documento de plan de estudios): la ULTIMA fila de
una tabla puede quedar fuera de la deteccion no por un problema de esta
heuristica, sino porque **Tesseract mismo** (su propio analisis de
bloques/parrafos/lineas, anterior a que esta funcion vea los datos) a
veces separa esa fila en 2 o 3 lineas/bloques distintos -- una por
columna -- en vez de reconocerla como una sola linea con huecos
horizontales, tipicamente cuando el contenido de esa fila especifica no
esta perfectamente alineado en la imagen o el layout original del
documento no es un grid perfectamente rectangular (confirmado con
`pytesseract.image_to_data()` real: 'Metodologia de la Investigacion',
'Economia' y 'Autoconocimiento' -- la sexta fila de la primera tabla de
ese documento -- llegan en 3 lineas/bloques de Tesseract distintos, cada
una con una sola palabra/frase, no en una sola linea con 3 columnas).
Como esta funcion opera sobre las lineas que Tesseract YA agrupo, ningun
ajuste de umbral de esta heuristica puede reunirlas de vuelta -- se
necesitaria reconstruir filas a partir de la posicion Y cruda de cada
palabra, ignorando el agrupamiento de Tesseract, que es exactamente el
tipo de solucion mas robusta (y mas compleja, con una libreria
especializada) que se descarto explicitamente al elegir esta heuristica
propia (ver el comentario 2026-07-31 sobre las tres opciones
presentadas). En vez de intentar adivinar/fusionar esas lineas sueltas
en la tabla (riesgo real de asignar mal una materia al cuatrimestre
equivocado), `reconstruir_texto_ocr()` solo las SENALA como advertencia
(ver el segundo valor que devuelve) para que se revisen a mano en
Revision -- el texto de salida no cambia.

Confianza por palabra (agregado 2026-08-01, a pedido del consultor:
"Nivel 1" de la propuesta sobre asistir la revision contra el original
con datos que Tesseract ya calcula pero antes se descartaban).
`pytesseract.image_to_data()` devuelve, ademas de la posicion de cada
palabra, una confianza de reconocimiento (0-100) que
`TesseractOcrEngine` unicamente usaba como filtro binario (">-1", es
decir "se reconocio algo") y despues tiraba -- el numero en si nunca
llegaba a ningun lado. Ahora `PalabraOcr.confianza` la conserva, y
`reconstruir_texto_ocr()` devuelve ademas los tramos del texto
reconstruido que corresponden a palabras por debajo de
`UMBRAL_CONFIANZA_BAJA` (ver `RangoBajaConfianza`), para que la interfaz
(Revision, Modulo 8) pueda resaltarlos -- dirigir la atencion del
revisor hacia las partes que el propio OCR reconoce como inciertas, en
vez de exigirle releer un documento completo de principio a fin. Esto
NO reemplaza el criterio humano (Documento Maestro, Modulo 13: control
humano) -- solo senala donde vale la pena mirar con mas cuidado."""
from __future__ import annotations

from pydantic import BaseModel

_UMBRAL_CLUSTER_COLUMNA = 3.0
"""Un hueco horizontal mayor a este multiplo de la altura de la linea se
interpreta como salto de columna, no como espacio entre palabras de la
misma frase: el espacio normal entre palabras suele ser una fraccion de
la altura de linea, mientras que el hueco entre columnas de una tabla
(el "gutter") suele ser de varias veces esa altura. Se usa un multiplo de
la altura -- no un pixelaje fijo -- para que el mismo umbral funcione
igual sin importar el DPI de rasterizacion o el tamano de fuente del
documento."""

_MIN_FILAS_TABLA = 3
"""Numero minimo de lineas consecutivas con el mismo numero de columnas
para tratarlas como una tabla, en vez de una coincidencia de un par de
lineas sueltas con la misma cantidad de "huecos grandes" por
casualidad."""

_MAX_PALABRAS_FRAGMENTO_COLA = 8
"""Tope de palabras para que una linea justo despues de una tabla se
considere un posible fragmento de fila incompleta (ver la limitacion
documentada arriba: Tesseract separa a veces la ultima fila de una
tabla en varias lineas de una sola columna). Sin este tope, CUALQUIER
parrafo normal que empiece justo despues de una tabla se marcaria como
advertencia -- la gran mayoria del texto plano tiene una sola columna
(ver `_columnas_de_linea`), asi que "una sola columna" por si solo no
es una senal suficiente; un fragmento de celda de tabla (nombre de una
materia, por ejemplo) es tipicamente corto, un parrafo real no."""

UMBRAL_CONFIANZA_BAJA = 60.0
"""Confianza (0-100, misma escala que devuelve `pytesseract.image_to_data()`)
por debajo de la cual una palabra se considera "de baja confianza" y se
resalta para el revisor. 60 es un punto medio deliberado -- ni tan alto
que casi todo el texto normal quede marcado (ruido, el revisor dejaria
de prestarle atencion a la senal), ni tan bajo que solo se marque texto
practicamente irreconocible. Es una constante de modulo, no un valor
fijo dentro de la logica, para poder ajustarla despues con datos reales
de uso sin tocar el resto de esta funcion."""


class PalabraOcr(BaseModel):
    """Una palabra reconocida por Tesseract, con su posicion (mismas
    unidades que `pytesseract.image_to_data()`: pixeles de la imagen
    rasterizada). `linea_id` es el trio (block_num, par_num, line_num)
    que Tesseract ya calcula -- se trata como un identificador opaco
    (solo importa si dos palabras comparten el mismo trio o no, nunca su
    valor concreto), asi que este modulo no necesita saber nada de como
    Tesseract arma internamente sus bloques/parrafos.

    `confianza` (agregado 2026-08-01): el valor de `conf` que
    `pytesseract.image_to_data()` calcula para esta palabra (0-100).
    Antes de este cambio, `TesseractOcrEngine` solo lo usaba para
    descartar entradas vacias (`conf > -1`) y tiraba el numero -- ver
    docstring del modulo. Por defecto 100.0 (confianza maxima) para que
    codigo que construye `PalabraOcr` sin conocer la confianza real
    (por ejemplo, pruebas existentes escritas antes de este campo seguir
    funcionando sin cambios."""

    texto: str
    izquierda: int
    arriba: int
    ancho: int
    alto: int
    linea_id: tuple[int, int, int]
    confianza: float = 100.0


class RangoBajaConfianza(BaseModel):
    """Un tramo del texto que devuelve `reconstruir_texto_ocr()`
    correspondiente a una palabra reconocida con confianza por debajo de
    `UMBRAL_CONFIANZA_BAJA`. `inicio`/`fin` son desplazamientos en
    caracteres dentro de ese texto -- mismo sistema de coordenadas que
    `Documento.mapa_paginas` y `HallazgoVerificacion.posicion`, para que
    la interfaz pueda reusar el mismo mecanismo de "desplazamiento en el
    Markdown" que ya usan esas otras dos piezas."""

    inicio: int
    fin: int
    confianza: float
    texto: str


def _agrupar_por_linea(palabras: list[PalabraOcr]) -> list[list[PalabraOcr]]:
    """Agrupa por `linea_id`, preservando el orden de PRIMERA aparicion de
    cada linea (el orden en que Tesseract ya devuelve las palabras, que es
    su propio orden de lectura de la pagina) y ordenando las palabras de
    cada linea por posicion horizontal."""
    lineas: dict[tuple[int, int, int], list[PalabraOcr]] = {}
    for palabra in palabras:
        lineas.setdefault(palabra.linea_id, []).append(palabra)
    return [sorted(grupo, key=lambda p: p.izquierda) for grupo in lineas.values()]


def _columnas_de_linea(linea: list[PalabraOcr]) -> list[str]:
    """Agrupa las palabras de una linea (ya ordenadas por posicion
    horizontal) en columnas segun el tamano del hueco entre cada palabra
    y la siguiente -- ver `_UMBRAL_CLUSTER_COLUMNA`."""
    if not linea:
        return []
    altura_linea = sum(p.alto for p in linea) / len(linea)
    umbral = altura_linea * _UMBRAL_CLUSTER_COLUMNA
    columnas: list[list[str]] = [[linea[0].texto]]
    fin_anterior = linea[0].izquierda + linea[0].ancho
    for palabra in linea[1:]:
        hueco = palabra.izquierda - fin_anterior
        if hueco > umbral:
            columnas.append([palabra.texto])
        else:
            columnas[-1].append(palabra.texto)
        fin_anterior = palabra.izquierda + palabra.ancho
    return [" ".join(columna) for columna in columnas]


def _escapar_celda(texto: str) -> str:
    """Una celda con '|' literal rompe la sintaxis de tabla Markdown si
    no se escapa."""
    return texto.replace("|", "\\|")


def _fila_markdown(celdas: list[str]) -> str:
    return "| " + " | ".join(_escapar_celda(c) for c in celdas) + " |"


def _posible_fragmento_de_fila(columnas: list[str], num_columnas_tabla: int) -> bool:
    """True si esta linea PODRIA ser un pedazo de la fila que le sigue a
    una tabla recien detectada, partido por Tesseract en mas de una
    linea -- ver la limitacion documentada en el modulo. Deliberadamente
    conservador (pocas columnas, pocas palabras) para no confundir un
    parrafo normal con un fragmento de celda."""
    if not (1 <= len(columnas) < num_columnas_tabla):
        return False
    texto_junto = " ".join(columnas)
    palabras = texto_junto.split()
    return 0 < len(palabras) <= _MAX_PALABRAS_FRAGMENTO_COLA


def _localizar_rangos_baja_confianza(palabras: list[PalabraOcr], texto: str) -> list[RangoBajaConfianza]:
    """Ubica, dentro de `texto` ya reconstruido, el tramo que corresponde
    a cada palabra de baja confianza -- en el mismo orden de lectura en
    que Tesseract devolvio las palabras (avanzando un cursor de busqueda
    hacia adelante en cada acierto). Deliberadamente simple en vez de
    rastrear el desplazamiento exacto a traves de cada transformacion de
    `reconstruir_texto_ocr()` (uniones de columna, filas de tabla
    Markdown, escapado de '|'...): a costa de no ser exacto si la MISMA
    palabra de baja confianza aparece mas de una vez seguida en el texto
    (caso raro), el peor resultado posible es resaltar una aparicion
    vecina de la misma palabra -- nunca una palabra distinta ni una
    excepcion."""
    rangos: list[RangoBajaConfianza] = []
    cursor = 0
    for palabra in palabras:
        if palabra.confianza >= UMBRAL_CONFIANZA_BAJA:
            continue
        # Si la palabra tiene '|' literal, en una celda de tabla habria
        # quedado escapada ("\|") -- se prueba esa variante primero
        # porque es la mas especifica; el texto sin escapar es el
        # respaldo (parrafo normal, o palabra con '|' fuera de una
        # tabla).
        candidatos = [_escapar_celda(palabra.texto), palabra.texto] if "|" in palabra.texto else [palabra.texto]
        inicio = -1
        objetivo = ""
        for candidato in candidatos:
            inicio = texto.find(candidato, cursor)
            if inicio == -1:
                inicio = texto.find(candidato)  # respaldo: buscar desde el inicio del texto.
            if inicio != -1:
                objetivo = candidato
                break
        if inicio == -1:
            continue  # palabra no localizable en el texto final -- no se resalta, no se rompe nada.
        fin = inicio + len(objetivo)
        rangos.append(RangoBajaConfianza(inicio=inicio, fin=fin, confianza=palabra.confianza, texto=palabra.texto))
        cursor = fin
    return rangos


def reconstruir_texto_ocr(palabras: list[PalabraOcr]) -> tuple[str, list[str], list[RangoBajaConfianza]]:
    """Reconstruye el texto reconocido por OCR, emitiendo como tabla
    Markdown cualquier grupo de al menos `_MIN_FILAS_TABLA` lineas
    consecutivas con el mismo numero de columnas (2 o mas) -- ver
    docstring del modulo para la heuristica completa y sus limitaciones
    conocidas. El resto del texto se reconstruye linea por linea, con una
    linea en blanco entre parrafos distintos (cambio de bloque/parrafo
    segun Tesseract) -- mismo criterio general que el texto plano que se
    obtenia antes de este cambio.

    Devuelve `(texto, advertencias, rangos_baja_confianza)`:
    `advertencias` (agregado 2026-07-31, PROY-6955_udl_3) senala, sin
    alterar el texto de salida, cuando justo despues de una tabla
    detectada aparecen 1 o mas lineas cortas que podrian ser una fila
    incompleta que Tesseract partio en varias lineas (ver la limitacion
    documentada arriba) -- para que se revise a mano en Revision en vez
    de perderse en silencio con `semaforo='verde'` y ninguna advertencia.
    `rangos_baja_confianza` (agregado 2026-08-01, ver
    `UMBRAL_CONFIANZA_BAJA`) ubica los tramos de `texto` que corresponden
    a palabras de baja confianza, para que la interfaz los resalte."""
    lineas = _agrupar_por_linea(palabras)
    columnas_por_linea = [_columnas_de_linea(linea) for linea in lineas]
    parrafo_de_cada_linea = [linea[0].linea_id[:2] for linea in lineas]

    salida: list[str] = []
    advertencias: list[str] = []
    i = 0
    n = len(columnas_por_linea)
    parrafo_anterior: tuple[int, ...] | None = None
    while i < n:
        num_columnas = len(columnas_por_linea[i])
        if num_columnas >= 2:
            fin = i + 1
            while fin < n and len(columnas_por_linea[fin]) == num_columnas:
                fin += 1
            if fin - i >= _MIN_FILAS_TABLA:
                if salida:
                    salida.append("")
                bloque = columnas_por_linea[i:fin]
                salida.append(_fila_markdown(bloque[0]))
                salida.append(_fila_markdown(["---"] * num_columnas))
                salida.extend(_fila_markdown(fila) for fila in bloque[1:])
                fragmentos: list[str] = []
                j = fin
                while (
                    j < n
                    and len(fragmentos) < num_columnas
                    and _posible_fragmento_de_fila(columnas_por_linea[j], num_columnas)
                ):
                    fragmentos.append(" ".join(columnas_por_linea[j]))
                    j += 1
                if fragmentos:
                    advertencias.append(
                        "Posible fila de tabla incompleta justo despues de una tabla "
                        f"detectada (Tesseract separo ese contenido en {len(fragmentos)} "
                        "linea(s) en vez de una fila de la tabla, revisar manualmente en "
                        "Revision): " + " / ".join(fragmentos)
                    )
                i = fin
                parrafo_anterior = None
                continue
        parrafo_actual = parrafo_de_cada_linea[i]
        if parrafo_anterior is not None and parrafo_actual != parrafo_anterior and salida:
            salida.append("")
        salida.append(" ".join(columnas_por_linea[i]))
        parrafo_anterior = parrafo_actual
        i += 1
    texto = "\n".join(salida)
    return texto, advertencias, _localizar_rangos_baja_confianza(palabras, texto)
