"""Motor OCR real via Tesseract: adaptado de RAG STUDIO
(infrastructure/extraction/ocr_engine.py: `TesseractOcrEngine`) --
copiado y ajustado como codigo propio (ADR-001, seccion 8), no
importado en vivo. pytesseract distingue dos fallos posibles: el
binario de Tesseract no esta instalado (`TesseractNotFoundError`), o
NINGUNO de los idiomas solicitados tiene su paquete instalado, lo que
produce un `TesseractError` con un mensaje sobre '<idioma>.traineddata'
(confirmado empiricamente en este entorno, que solo trae los paquetes
'eng'/'osd').

Importante -- comportamiento real confirmado con un lang combinado
('spa+eng'): si al menos uno de los idiomas de la lista si tiene su
paquete instalado, Tesseract ignora en silencio los que faltan y
reconoce el texto con el resto, sin lanzar excepcion. Es decir, el
idioma por defecto de este adaptador ('spa+eng') NO falla en un
entorno que solo tiene 'eng' instalado -- solo fallaria si se pidiera
'spa' a solas (ver test_tesseract_ocr_engine.py). Ambos fallos reales
(binario ausente, o todos los idiomas solicitados sin paquete) se
unifican en domain.documents.exceptions.OcrEngineUnavailableError --
quien llama no necesita conocer pytesseract para reaccionar a un motor
no disponible.

Deteccion de tablas (bug real reportado 2026-07-31, ver docstring de
domain.documents.ocr_table_reconstruction): antes de este cambio se
llamaba a `pytesseract.image_to_string()`, que devuelve el texto de la
pagina completa sin ninguna nocion de columnas -- una tabla (por
ejemplo, materias agrupadas por cuatrimestre en columnas) terminaba con
el contenido de todas las columnas concatenado en el mismo renglon.
Ahora se usa `pytesseract.image_to_data()` (mismo binario, mismos
fallos posibles, pero con la posicion de cada palabra reconocida) y se
delega la reconstruccion a `reconstruir_texto_ocr()`, una funcion pura
de domain que agrupa palabras en columnas/filas y emite tablas
detectadas como Markdown -- ver esa funcion para la heuristica completa
y sus limitaciones conocidas.

`image_to_text()` devuelve `(texto, advertencias)` desde 2026-07-31
(analisis real de PROY-6955_udl_3): `reconstruir_texto_ocr()` puede
detectar una posible fila de tabla incompleta (Tesseract partiendola en
varias lineas) sin poder reconstruirla con seguridad -- ver su
docstring -- asi que la senala como advertencia en vez de arriesgarse a
adivinar mal la columna correcta.

Confianza por palabra (agregado 2026-08-01): `pytesseract.image_to_data()`
ya calculaba un valor `conf` (0-100) por palabra, pero antes de este
cambio solo se usaba como filtro binario (`> -1`, "se reconocio algo") y
el numero se descartaba de inmediato -- nunca llegaba a `PalabraOcr` ni
a ningun lado mas alla de esa comprobacion. Ahora se conserva
(`PalabraOcr.confianza`) y `reconstruir_texto_ocr()` devuelve ademas los
tramos de baja confianza -- ver
domain.documents.ocr_table_reconstruction para el resto del mecanismo.

Preprocesamiento de imagen + recuperacion de bandas de color (agregado
2026-08-24, a pedido explicito del consultor: "mejorar la capacidad
OCR", tras comparar con RAG STUDIO y con un tutorial de OpenCV/
Pytesseract). Hasta este cambio, la imagen llegaba a
`pytesseract.image_to_data()` tal cual la entregaba
`PdfOcrExtractor`/`ImageOcrExtractor` -- sin escala de grises, sin
reduccion de ruido, sin binarizar. RAG STUDIO ya habia resuelto este
mismo problema, adaptado aqui como codigo propio (ver
`_preprocesar_para_ocr`/`_umbral_otsu`/`_detectar_bandas_de_color`/
`_recuperar_texto_de_bandas_de_color`, cada una con su nota de origen):
escala de grises + filtro de medianas (ruido de escaneo) + binarizacion
con el umbral de Otsu (adaptativo por imagen, no un numero fijo), mas
la deteccion/recuperacion de bandas horizontales de color saturado
(tipicamente encabezados de seccion con fondo de marca) que Tesseract
tiende a omitir por completo sin ningun aviso. Ambas piezas siguen el
mismo criterio ya establecido en RAG STUDIO: solo Pillow, sin agregar
numpy/OpenCV como dependencia nueva -- evaluado y descartado
explicitamente (ver conversacion con el consultor, 2026-08-24): la
ganancia de OpenCV frente a lo que ya resuelve Pillow no justifica una
dependencia mas pesada para una herramienta de uso personal.

Correccion de inclinacion / deskew (agregado en la misma fecha, esta
si es una pieza propia de RAG Content Studio -- RAG STUDIO tampoco la
tiene): un documento escaneado o fotografiado ligeramente torcido
produce lineas de texto que no quedan horizontales, lo que Tesseract
reconoce peor cuanto mayor es la inclinacion. `_detectar_angulo_
inclinacion` prueba un rango acotado de angulos candidatos (+-5 grados,
en pasos de 0.5) sobre una miniatura de la imagen ya binarizada y elige
el que produce el perfil de proyeccion horizontal mas "nitido" (mayor
contraste fila a fila -- una pagina bien alineada tiene filas muy
oscuras dentro de una linea de texto y casi blancas entre lineas; una
pagina inclinada difumina ese patron). Si ningun angulo candidato
mejora claramente al angulo cero, no se rota nada -- evita introducir
una rotacion espuria en una pagina que ya estaba derecha. Alcance
deliberadamente acotado: no corrige paginas al reves ni giradas 90
grados (un problema distinto, de mayor magnitud, fuera de esta mejora)."""
from __future__ import annotations

import io

import pytesseract
from PIL import Image, ImageChops, ImageFilter

from domain.documents.exceptions import OcrEngineUnavailableError
from domain.documents.ocr_table_reconstruction import PalabraOcr, RangoBajaConfianza, reconstruir_texto_ocr
from domain.documents.ports import OcrEngine

_DEFAULT_LANG = "spa+eng"
"""Espanol primero, ingles como respaldo -- mismo criterio que RAG
STUDIO (la mayoria de los documentos del proyecto son en espanol, pero
algunos anexos/citas vienen en ingles). ADR-001, seccion 14.1."""

# -- Preprocesamiento (escala de grises + ruido + binarizacion) --------
# Adaptado de RAG STUDIO (infrastructure/extraction/ocr_engine.py,
# tarea de la Fase -1 de RAG 4, validada empiricamente contra un PDF
# escaneado real, Licenciatura/ingcom.pdf): sin preprocesamiento,
# Tesseract reconocia 1 de 14 encabezados de cuatrimestre (bandas de
# color, ver mas abajo); con escala de grises + filtro de medianas +
# binarizacion Otsu, se recuperaron 8-9 de 14, sin perder contenido del
# resto de la pagina.
_TAMANO_FILTRO_MEDIANA_RUIDO = 3

# -- Bandas de color (encabezados con fondo de marca) -------------------
# Adaptado de RAG STUDIO (misma fuente, Ronda 22: hallazgo real con
# ingcom.pdf): Tesseract, al reconocer una pagina completa, suele
# clasificar una banda horizontal con fondo de color saturado (un
# encabezado de seccion en un color de marca) como "no es texto" y la
# omite por completo, sin ninguna advertencia. Recortar esa banda por
# separado y reconocerla con --psm 6 si recupera texto, al menos
# parcialmente. Los umbrales de abajo se calibraron en RAG STUDIO
# contra ese documento real.
_SATURACION_MINIMA_BANDA_COLOR = 40
_RANGO_VALOR_BANDA_COLOR = (100, 250)
_FRACCION_MINIMA_FILA_BANDA_COLOR = 0.10
_ALTURA_MINIMA_BANDA_COLOR_PX = 12
_ALTURA_MAXIMA_BANDA_COLOR_PX = 100
_MAX_BANDAS_COLOR_POR_PAGINA = 10
"""Limite de seguridad: una pagina con mas bandas de color detectadas
que esto probablemente no sigue el patron "encabezado de seccion en un
color de marca" (ruido, una plantilla con fondo de color en general, o
una fotografia) -- se descarta por completo en vez de lanzar decenas de
reconocimientos de OCR adicionales de bajo valor por pagina."""
_MARGEN_BANDA_COLOR_PX = 8
_CONFIG_PSM_BANDA_COLOR = "--psm 6"
_CONFIANZA_TEXTO_RECUPERADO_DE_BANDA = 0.0
"""Confianza que se asigna a TODO el texto recuperado de una banda de
color, sin importar el valor de `conf` que reporte Tesseract para cada
palabra en ese recorte -- a proposito, no se reusa el numero real de
Tesseract: esta ruta de recuperacion (recorte angosto, PSM distinto al
de la pagina completa) ya es en si misma un mejor esfuerzo, tal como lo
documenta RAG STUDIO ("reconocimiento OCR de confianza baja, puede
contener ruido"), independientemente de que Tesseract reporte un
numero alto para alguna palabra suelta -- 0.0 garantiza que todo el
bloque quede siempre por debajo de `UMBRAL_CONFIANZA_BAJA` y se
resalte para el revisor (Nivel 1, ver ocr_table_reconstruction)."""

# -- Correccion de inclinacion / deskew (pieza propia de este proyecto) -
_ANGULOS_CANDIDATOS_DESKEW_GRADOS = [paso / 2 for paso in range(-10, 11) if paso != 0]
"""De -5.0 a 5.0 grados en pasos de 0.5 (sin el 0, que ya es el punto
de referencia con el que se compara) -- rango acotado a proposito: una
pagina escaneada/fotografiada torcida a mano rara vez pasa de unos
pocos grados; un giro mayor (90 grados, al reves) es un problema
distinto que esta mejora no intenta resolver (ver docstring del
modulo)."""
_MEJORA_MINIMA_DESKEW = 1.05
"""El angulo candidato ganador debe superar el puntaje del angulo cero
por al menos un 5% para aplicarse -- si ninguno lo hace, la pagina ya
estaba razonablemente derecha y rotarla solo agregaria un artefacto de
interpolacion sin beneficio real."""
_ANCHO_MAXIMO_MINIATURA_DESKEW_PX = 700
"""La deteccion del angulo se hace sobre una miniatura, no la imagen
completa: el angulo de inclinacion no depende de la resolucion, y
probar ~20 angulos candidatos sobre una pagina completa (posiblemente
varios miles de pixeles de ancho) seria innecesariamente lento -- una
miniatura de a lo sumo 700px de ancho ya conserva el patron de lineas
de texto necesario para medir el angulo con suficiente precision."""


def _umbral_otsu(histograma: list[int]) -> int:
    """Umbral optimo de binarizacion (metodo de Otsu) a partir del
    histograma de 256 niveles de una imagen en escala de grises
    (`Image.histogram()`). Adaptado de RAG STUDIO -- implementacion en
    Python puro (sin numpy/OpenCV, ver docstring del modulo), viable
    porque el histograma ya resume la imagen completa a 256 valores; el
    costo de las sumas acumuladas es insignificante frente al propio
    reconocimiento de Tesseract. Adaptativo por imagen (a diferencia de
    un umbral fijo) porque el contraste real de un documento escaneado/
    rasterizado varia de una fuente a otra."""
    total = sum(histograma)
    if total == 0:
        return 128
    suma_total = sum(nivel * cuenta for nivel, cuenta in enumerate(histograma))
    suma_bajo = 0
    peso_bajo = 0
    mejor_varianza = -1.0
    # Cuando varios niveles consecutivos empatan en la varianza maxima
    # (tipico de un histograma bimodal con un valle plano de densidad
    # cero entre los dos picos), el punto medio del tramo empatado es
    # un umbral mas razonable que el primer nivel del tramo.
    mejor_inicio_rango = 0
    mejor_fin_rango = 0
    for nivel, cuenta in enumerate(histograma):
        peso_bajo += cuenta
        if peso_bajo == 0:
            continue
        peso_alto = total - peso_bajo
        if peso_alto == 0:
            break
        suma_bajo += nivel * cuenta
        media_bajo = suma_bajo / peso_bajo
        media_alto = (suma_total - suma_bajo) / peso_alto
        varianza_entre = peso_bajo * peso_alto * (media_bajo - media_alto) ** 2
        if varianza_entre > mejor_varianza:
            mejor_varianza = varianza_entre
            mejor_inicio_rango = mejor_fin_rango = nivel
        elif varianza_entre == mejor_varianza:
            mejor_fin_rango = nivel
    return (mejor_inicio_rango + mejor_fin_rango) // 2


def _perfil_de_proyeccion(imagen_binaria: "Image.Image") -> float:
    """Puntaje de nitidez del perfil de proyeccion horizontal: la suma
    de las diferencias absolutas entre filas consecutivas del promedio
    de brillo por fila. Una imagen bien alineada tiene un perfil con
    picos y valles marcados (una fila dentro de una linea de texto es
    oscura, una fila entre lineas es casi blanca) -- un contraste de
    fila a fila alto. Una imagen inclinada difumina ese perfil (cada
    fila mezcla fragmentos de varias lineas de texto), dando un
    contraste mucho mas bajo. Misma tecnica que
    `_detectar_bandas_de_color` para el perfil por fila: reducir la
    imagen a una sola columna con `Image.BOX` (promedia en C, no
    iterando pixel por pixel en Python)."""
    _, alto = imagen_binaria.size
    if alto < 2:
        return 0.0
    columna = imagen_binaria.resize((1, alto), Image.Resampling.BOX)
    valores = list(columna.getdata())
    return float(sum(abs(valores[i] - valores[i - 1]) for i in range(1, len(valores))))


def _detectar_angulo_inclinacion(imagen_binaria: "Image.Image") -> float:
    """Devuelve el angulo (grados) que mejor endereza `imagen_binaria`,
    o `0.0` si ningun candidato mejora claramente sobre no rotar nada
    -- ver `_ANGULOS_CANDIDATOS_DESKEW_GRADOS`/`_MEJORA_MINIMA_DESKEW`.
    La busqueda se hace sobre una miniatura (ver
    `_ANCHO_MAXIMO_MINIATURA_DESKEW_PX`); el angulo encontrado es el
    mismo sin importar la resolucion de la imagen original."""
    ancho, alto = imagen_binaria.size
    if ancho > _ANCHO_MAXIMO_MINIATURA_DESKEW_PX and ancho > 0:
        factor = _ANCHO_MAXIMO_MINIATURA_DESKEW_PX / ancho
        miniatura = imagen_binaria.resize(
            (_ANCHO_MAXIMO_MINIATURA_DESKEW_PX, max(1, round(alto * factor))),
            Image.Resampling.BILINEAR,
        )
    else:
        miniatura = imagen_binaria

    puntaje_base = _perfil_de_proyeccion(miniatura)
    mejor_angulo = 0.0
    mejor_puntaje = puntaje_base
    for angulo in _ANGULOS_CANDIDATOS_DESKEW_GRADOS:
        rotada = miniatura.rotate(angulo, resample=Image.Resampling.BILINEAR, fillcolor=255)
        puntaje = _perfil_de_proyeccion(rotada)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_angulo = angulo
    if mejor_puntaje < puntaje_base * _MEJORA_MINIMA_DESKEW:
        return 0.0
    return mejor_angulo


def _corregir_inclinacion(imagen_binaria: "Image.Image") -> "Image.Image":
    """Rota `imagen_binaria` para corregir su inclinacion si
    `_detectar_angulo_inclinacion` encuentra una mejora clara; la
    devuelve tal cual si no. El relleno de las esquinas que deja al
    descubierto la rotacion es blanco (255), el mismo color que el
    fondo ya binarizado."""
    angulo = _detectar_angulo_inclinacion(imagen_binaria)
    if angulo == 0.0:
        return imagen_binaria
    return imagen_binaria.rotate(angulo, resample=Image.Resampling.BICUBIC, fillcolor=255)


def _preprocesar_para_ocr(imagen: "Image.Image") -> "Image.Image":
    """Preprocesamiento antes de Tesseract: escala de grises, reduccion
    de ruido leve (filtro de medianas), binarizacion con el umbral de
    Otsu, y correccion de inclinacion -- ver las notas junto a cada
    constante para el criterio y la validacion empirica de cada paso.
    Recibe y devuelve una imagen PIL nueva; nunca modifica `imagen` en
    el lugar, porque quien llama todavia necesita la imagen ORIGINAL a
    color para `_detectar_bandas_de_color` (que depende de saturacion/
    valor HSV -- una imagen ya binarizada no tiene esa informacion)."""
    escala_de_grises = imagen.convert("L")
    sin_ruido = escala_de_grises.filter(ImageFilter.MedianFilter(size=_TAMANO_FILTRO_MEDIANA_RUIDO))
    umbral = _umbral_otsu(sin_ruido.histogram())
    binarizada = sin_ruido.point(lambda p: 255 if p > umbral else 0)
    return _corregir_inclinacion(binarizada)


def _detectar_bandas_de_color(imagen: "Image.Image") -> list[tuple[int, int]]:
    """Devuelve los rangos verticales (y_inicio, y_fin) en pixeles de
    las bandas horizontales de `imagen` cuyo fondo es mayormente de
    color saturado (ni texto negro/gris sobre blanco, que tiene
    saturacion baja, ni blanco puro). Adaptado de RAG STUDIO -- usa
    unicamente PIL (sin numpy): el filtrado por saturacion/valor se
    hace con `Image.point`, y el perfil de color por fila con un
    `resize` a una sola columna (`Image.BOX` promedia, en C, en vez de
    iterar pixel por pixel en Python).

    Ya filtra por una altura plausible de una sola banda de encabezado
    (`_ALTURA_MINIMA_BANDA_COLOR_PX`/`_ALTURA_MAXIMA_BANDA_COLOR_PX`) --
    un logotipo o una fotografia a color producen bandas mucho mas
    altas o irregulares, que se descartan a proposito en vez de
    intentar reconocerlas como texto."""
    hsv = imagen.convert("RGB").convert("HSV")
    saturacion, _, valor = hsv.split()
    mascara_saturada = saturacion.point(lambda p: 255 if p > _SATURACION_MINIMA_BANDA_COLOR else 0)
    valor_bajo, valor_alto = _RANGO_VALOR_BANDA_COLOR
    mascara_valor_medio = valor.point(lambda p: 255 if valor_bajo < p < valor_alto else 0)
    mascara_color = ImageChops.multiply(mascara_saturada, mascara_valor_medio)

    _, alto = imagen.size
    perfil_por_fila = mascara_color.resize((1, alto), Image.Resampling.BOX)
    fraccion_por_fila = [nivel / 255.0 for nivel in list(perfil_por_fila.getdata())]

    bandas: list[tuple[int, int]] = []
    inicio_banda: int | None = None
    for y, fraccion in enumerate(fraccion_por_fila):
        es_fila_de_color = fraccion > _FRACCION_MINIMA_FILA_BANDA_COLOR
        if es_fila_de_color and inicio_banda is None:
            inicio_banda = y
        elif not es_fila_de_color and inicio_banda is not None:
            bandas.append((inicio_banda, y))
            inicio_banda = None
    if inicio_banda is not None:
        bandas.append((inicio_banda, alto))

    bandas_plausibles = [
        (y0, y1) for y0, y1 in bandas if _ALTURA_MINIMA_BANDA_COLOR_PX <= (y1 - y0) <= _ALTURA_MAXIMA_BANDA_COLOR_PX
    ]
    # Auditoria 2026-08-24: esto truncaba a las primeras
    # _MAX_BANDAS_COLOR_POR_PAGINA en vez de descartar la pagina por
    # completo como documenta la constante -- una pagina con mas bandas
    # "plausibles" que el limite (tipicamente una fotografia o una
    # plantilla con franjas de color, justo el caso que el limite quiere
    # excluir) seguia disparando hasta el limite de reconocimientos OCR
    # adicionales de bajo valor en vez de ninguno.
    if len(bandas_plausibles) > _MAX_BANDAS_COLOR_POR_PAGINA:
        return []
    return bandas_plausibles


class TesseractOcrEngine(OcrEngine):
    def __init__(self, lang: str = _DEFAULT_LANG, preprocess: bool = True):
        self._lang = lang
        # Ver _preprocesar_para_ocr: mejora validada empiricamente en
        # RAG STUDIO, activada por defecto. Se deja como parametro -- no
        # como comportamiento incondicional -- por si algun documento
        # real regresionara con la binarizacion/deskew (por ejemplo, un
        # escaneo ya muy limpio donde el preprocesamiento solo agregue
        # costo sin beneficio), no porque se haya observado una
        # regresion real todavia. Correccion de precision, auditoria
        # 2026-08-24: hoy este parametro NO es ajustable sin tocar
        # codigo -- la unica instanciacion en produccion es
        # `TesseractOcrEngine()` sin argumentos, en `app/bootstrap.py`,
        # y no hay ninguna opcion de configuracion/UI que llegue hasta
        # aqui. Mitigar una regresion real requeriria hoy editar
        # `app/bootstrap.py` y volver a desplegar; exponerlo como opcion
        # de configuracion queda pendiente para si alguna vez hace
        # falta de verdad, no antes (mismo criterio de "no agregar
        # configurabilidad que nadie pidio" del resto del proyecto).
        self._preprocess = preprocess

    def _recuperar_texto_de_bandas_de_color(self, imagen: "Image.Image") -> tuple[list[str], str | None]:
        """Recorta cada banda de color detectada
        (`_detectar_bandas_de_color`) por separado y la reconoce con
        `--psm 6` -- ver la nota junto a esa funcion. Adaptado de RAG
        STUDIO, incluyendo un hallazgo especifico de esa herramienta
        (su "Ronda 74"): a diferencia de la pagina completa, el recorte
        NUNCA se preprocesa -- en un recorte chico (una sola banda,
        unas pocas decenas de pixeles de alto) el filtro de medianas
        borra los propios trazos delgados del texto en vez de solo
        quitar ruido, y Tesseract termina sin reconocer nada.

        Es una recuperacion de mejor esfuerzo, no una ruta critica: un
        fallo puntual de Tesseract al reconocer UNA banda (segundo
        try/except de abajo, con `# nosec B112`: es una llamada externa
        real, con fallos esperables) se ignora en silencio para esa
        banda, sin afectar el resto ni el resultado principal de
        `image_to_text`. Devuelve ademas una advertencia opcional (no
        `None`) cuando `_detectar_bandas_de_color` en si misma falla --
        auditoria 2026-08-24: esa funcion es PIL puro sin E/S, asi que
        cualquier excepcion que produzca es casi con certeza un bug de
        programacion, no un fallo externo esperable; capturarla con
        `except Exception: return []` sin dejar rastro (como se hacia
        antes) habria escondido una regresion futura indefinidamente en
        vez de solo "no habia bandas de color esta vez"."""
        try:
            bandas = _detectar_bandas_de_color(imagen)
        except Exception as exc:
            return [], f"No se pudo analizar bandas de color en esta imagen: {exc}"
        if not bandas:
            return [], None
        ancho, alto = imagen.size
        recuperado: list[str] = []
        for y0, y1 in bandas:
            arriba = max(0, y0 - _MARGEN_BANDA_COLOR_PX)
            abajo = min(alto, y1 + _MARGEN_BANDA_COLOR_PX)
            try:
                recorte = imagen.crop((0, arriba, ancho, abajo))
                texto = pytesseract.image_to_string(recorte, lang=self._lang, config=_CONFIG_PSM_BANDA_COLOR).strip()
            except Exception:  # nosec B112
                # Una banda con error de Tesseract no debe descartar las demas
                # bandas ni el resultado principal de image_to_text.
                continue
            if texto:
                recuperado.append(texto)
        return recuperado, None

    def image_to_text(self, image_bytes: bytes) -> tuple[str, list[str], list[RangoBajaConfianza]]:
        try:
            imagen = Image.open(io.BytesIO(image_bytes))
            imagen.load()
        except OSError as exc:
            # Auditoria 2026-08-24: Image.open() decodifica de forma
            # perezosa -- confirmado empiricamente que una imagen PNG
            # truncada (encabezado valido, datos incompletos) NO falla
            # en open(), sino recien en la primera operacion que fuerza
            # a leer los pixeles. Antes, esa operacion era
            # `_preprocesar_para_ocr()` (mas abajo, fuera de cualquier
            # try/except), asi que una imagen corrupta-pero-abrible
            # producia un OSError crudo sin capturar -- justo el crash
            # de proceso externo que este motor dice evitar en su
            # docstring de modulo. `imagen.load()` fuerza la
            # decodificacion aqui mismo, en el unico lugar de este
            # metodo pensado para traducir fallos de imagen a un error
            # de dominio accionable (UnidentifiedImageError, el caso ya
            # cubierto de "no es una imagen", es tambien un OSError en
            # Pillow, asi que este unico bloque cubre ambos casos).
            raise OcrEngineUnavailableError(
                f"Los datos recibidos no son una imagen OCR valida (puede "
                f"estar incompleta o corrupta): {exc}"
            ) from exc

        # _detectar_bandas_de_color (dentro de
        # _recuperar_texto_de_bandas_de_color, mas abajo) necesita la
        # imagen a color ORIGINAL -- se preprocesa solo una copia para
        # el reconocimiento principal, nunca `imagen` en el lugar.
        imagen_para_reconocer = _preprocesar_para_ocr(imagen) if self._preprocess else imagen

        try:
            datos = pytesseract.image_to_data(imagen_para_reconocer, lang=self._lang, output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrEngineUnavailableError(
                "El binario de Tesseract OCR no esta instalado en este sistema "
                "operativo -- ver ADR-001, seccion 14.1, para el paquete requerido."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise OcrEngineUnavailableError(
                f"Tesseract no pudo reconocer el texto con el idioma '{self._lang}' "
                f"(probablemente falta el paquete de idioma correspondiente, por "
                f"ejemplo 'tesseract-ocr-spa'): {exc}"
            ) from exc

        palabras = [
            PalabraOcr(
                texto=texto,
                izquierda=datos["left"][i],
                arriba=datos["top"][i],
                ancho=datos["width"][i],
                alto=datos["height"][i],
                linea_id=(datos["block_num"][i], datos["par_num"][i], datos["line_num"][i]),
                confianza=float(datos["conf"][i]),
            )
            for i, texto in enumerate(datos["text"])
            if float(datos["conf"][i]) > -1 and texto.strip()
        ]
        texto_reconstruido, advertencias, rangos = reconstruir_texto_ocr(palabras)
        # reconstruir_texto_ocr() ubica los rangos contra el texto SIN
        # recortar -- si strip() quita algo del inicio, los
        # desplazamientos de los rangos deben correrse la misma cantidad
        # para seguir apuntando al caracter correcto en el texto final.
        texto_final = texto_reconstruido.strip()
        recorte_inicial = len(texto_reconstruido) - len(texto_reconstruido.lstrip())
        rangos_ajustados = [
            RangoBajaConfianza(
                inicio=rango.inicio - recorte_inicial,
                fin=rango.fin - recorte_inicial,
                confianza=rango.confianza,
                texto=rango.texto,
            )
            for rango in rangos
            if rango.inicio >= recorte_inicial and rango.fin <= recorte_inicial + len(texto_final)
        ]

        # Recuperacion de bandas de color (adaptado de RAG STUDIO,
        # Ronda 22): incondicional, no depende de self._preprocess --
        # es una recuperacion adicional sobre la imagen ORIGINAL a
        # color, independiente del preprocesamiento de la pagina
        # completa. El texto recuperado se agrega al final, en un
        # bloque marcado, y cada linea recuperada se registra ademas
        # como RangoBajaConfianza (Nivel 1) para que la interfaz la
        # resalte igual que cualquier otro tramo de baja confianza.
        recuperado, aviso_deteccion_bandas = self._recuperar_texto_de_bandas_de_color(imagen)
        if aviso_deteccion_bandas is not None:
            advertencias = advertencias + [aviso_deteccion_bandas]
        if recuperado:
            cursor_bloque = len(texto_final)
            texto_final += (
                "\n\n[Texto adicional recuperado de bandas de color -- "
                "reconocimiento OCR de confianza baja, puede contener ruido]\n"
                + "\n".join(recuperado)
            )
            for linea in recuperado:
                inicio = texto_final.find(linea, cursor_bloque)
                if inicio == -1:
                    continue
                fin = inicio + len(linea)
                rangos_ajustados.append(
                    RangoBajaConfianza(
                        inicio=inicio, fin=fin, confianza=_CONFIANZA_TEXTO_RECUPERADO_DE_BANDA, texto=linea
                    )
                )
                cursor_bloque = fin
            advertencias = advertencias + [
                f"Se recupero texto adicional de {len(recuperado)} banda(s) de color en esta "
                "imagen (encabezados con fondo de color que Tesseract omite normalmente) -- "
                "reconocimiento de confianza baja, revisar manualmente contra el original."
            ]

        # Ajuste final -- auditoria 2026-08-24: si la pagina no producia
        # texto de cuerpo (`texto_reconstruido` vacio) pero si se
        # recuperaba texto de una banda de color, `texto_final` quedaba
        # empezando en "\n\n[Texto adicional...", con espacio en blanco
        # al inicio. Quien llama (PdfOcrExtractor/ImageOcrExtractor) le
        # aplica ademas su propio `.strip()` defensivo antes de guardar
        # el texto, lo que corria las posiciones reales pero dejaba los
        # `RangoBajaConfianza` ya calculados apuntando a los caracteres
        # equivocados -- el resaltado ambar de esa pagina quedaba
        # desalineado (en el peor caso, descartado en silencio por caer
        # fuera del texto). Se garantiza aqui que el texto devuelto por
        # este metodo nunca tenga espacio en blanco al inicio/final, con
        # el mismo criterio de recorte-y-reajuste que ya se aplica mas
        # arriba para `texto_reconstruido`.
        recorte_final_inicio = len(texto_final) - len(texto_final.lstrip())
        texto_final = texto_final.strip()
        if recorte_final_inicio:
            rangos_ajustados = [
                RangoBajaConfianza(
                    inicio=rango.inicio - recorte_final_inicio,
                    fin=rango.fin - recorte_final_inicio,
                    confianza=rango.confianza,
                    texto=rango.texto,
                )
                for rango in rangos_ajustados
                if rango.inicio >= recorte_final_inicio and rango.fin <= recorte_final_inicio + len(texto_final)
            ]

        return texto_final, advertencias, rangos_ajustados


def ocr_dependencies_available(lang: str = _DEFAULT_LANG) -> bool:
    """Prueba barata para diagnostico/arranque (no se usa en la ruta de
    extraccion en si, que siempre debe fallar con
    OcrEngineUnavailableError si algo falta, nunca en silencio) -- mismo
    helper que RAG STUDIO expone para que la interfaz pueda advertir
    antes de que el usuario intente procesar un documento."""
    try:
        idiomas_instalados = set(pytesseract.get_languages(config=""))
    except pytesseract.TesseractNotFoundError:
        return False
    return all(idioma in idiomas_instalados for idioma in lang.split("+"))
