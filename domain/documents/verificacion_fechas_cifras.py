"""Modulo 8 (verificacion automatica de fechas/cifras, Documento
Maestro seccion 4.6: fila 8 "Revision contra originales" -- "Verificar
fidelidad" mediante "navegacion sincronizada, correccion, comentarios,
incidencias, verificacion de fechas/cifras y aprobacion").

Esta pieza NO valida que una fecha o cifra sea correcta -- no hay forma
de saberlo sin el original delante del revisor, y la seccion de
prohibiciones del Documento Maestro es explicita: "no inventar fechas,
vigencias..." tampoco aplica aqui en sentido inverso (la herramienta no
inventa un veredicto de correccion). Lo que hace es detectar y ubicar
los fragmentos del Markdown extraido que con mas probabilidad necesitan
cotejarse contra el original, para que el panel de revision (Modulo 8,
UI) pueda listarlos y saltar a ellos -- la decision de si estan bien
sigue siendo siempre del humano.

Funcion pura, sin dependencias de infrastructure ni de otros contextos
acotados: mismo principio ya usado en
domain.incidents.entities.filtrar_criticas_abiertas().

Nivel 2 (validaciones numericas), 2026-08-01, a pedido explicito del
consultor tras analizar la fatiga visual del revisor al cotejar
volumenes altos de documentos (ver bitacora): ademas de detectar y
ubicar fechas/cifras (arriba), esta pieza ahora tambien marca las
FECHAS que son imposibles segun el calendario -- por ejemplo
"31/04/2026" (abril solo tiene 30 dias) o "29/02/2026" (2026 no es
bisiesto). Esto SI es una validacion real (no una deteccion mas): una
fecha invalida es un hecho objetivo del calendario, no una opinion, asi
que no rompe el principio de "la herramienta no inventa un veredicto de
correccion" de arriba -- ese principio sigue aplicando a si la fecha es
la CORRECTA para el contrato, algo que solo el original puede confirmar.
"""
from __future__ import annotations

import calendar
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class TipoHallazgoVerificacion(str, Enum):
    FECHA = "fecha"
    CIFRA = "cifra"


class HallazgoVerificacion(BaseModel):
    """Un fragmento del Markdown que parece una fecha o una cifra."""

    tipo: TipoHallazgoVerificacion
    texto: str
    posicion: int
    """Desplazamiento en caracteres donde comienza el hallazgo dentro
    del Markdown analizado -- mismo sistema de coordenadas que
    `Documento.mapa_paginas`, para que la UI pueda reusar el mismo
    mecanismo de salto de cursor al mostrar la lista de hallazgos."""
    advertencia: Optional[str] = None
    """Nivel 2: mensaje corto si el propio hallazgo es imposible segun
    el calendario (solo aplica a FECHA, ver `_advertencia_para_texto_de_
    fecha()`) -- `None` es el caso normal (fecha plausible, o hallazgo
    de tipo CIFRA, que nunca se valida aqui)."""


_MESES = (
    "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
)

_PATRON_FECHA = re.compile(
    r"""
    \b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b              # 12/05/2026, 12-05-26
    |\b\d{4}-\d{1,2}-\d{1,2}\b                      # 2026-05-12 (ISO)
    |\b\d{1,2}\s+de\s+(?:""" + _MESES + r""")\s+de\s+\d{4}\b   # 12 de mayo de 2026
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PATRON_CIFRA = re.compile(
    r"""
    [$€]\s?\d[\d.,]*\d                     # $1,234.56 / € 1.234,56
    |\b\d[\d.,]*\d\s?%                      # 45.5% / 45,5 %
    |\b\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?\b  # 1,234,567.89 (separadores de miles)
    """,
    re.VERBOSE,
)


# -- Nivel 2: validacion de calendario para las fechas ya detectadas ---
# Se re-analiza el TEXTO exacto que ya encontro `_PATRON_FECHA` (nunca
# se cambia esa deteccion) con un patron dedicado por formato -- asi
# cada uno puede tener sus propios grupos con nombre (dia/mes/anio) sin
# chocar entre si, cosa que `re` no permite dentro de una sola
# alternancia.
_PATRON_FECHA_NUMERICA = re.compile(r"^(?P<dia>\d{1,2})[/-](?P<mes>\d{1,2})[/-](?P<anio>\d{2,4})$")
_PATRON_FECHA_ISO = re.compile(r"^(?P<anio>\d{4})-(?P<mes>\d{1,2})-(?P<dia>\d{1,2})$")
_PATRON_FECHA_TEXTUAL = re.compile(
    r"^(?P<dia>\d{1,2})\s+de\s+(?P<mes>" + _MESES + r")\s+de\s+(?P<anio>\d{4})$",
    re.IGNORECASE,
)
_MESES_EN_ORDEN = _MESES.split("|")


def _expandir_anio(anio_texto: str) -> int:
    """Un anio de 2 digitos ('26') se interpreta como 2000+anio -- el
    unico rango realista para los documentos de este proyecto (nunca
    19xx); ver Documento Maestro."""
    anio = int(anio_texto)
    return 2000 + anio if len(anio_texto) == 2 else anio


def _advertencia_fecha_invalida(dia: int, mes: int, anio: int) -> str | None:
    if not 1 <= mes <= 12:
        return f"mes fuera de rango (1-12): {mes}"
    dias_del_mes = calendar.monthrange(anio, mes)[1]
    if not 1 <= dia <= dias_del_mes:
        return f"dia fuera de rango para ese mes ({mes}/{anio} tiene {dias_del_mes} dias): {dia}"
    return None


def _advertencia_para_texto_de_fecha(texto: str) -> str | None:
    """Interpreta `texto` (el fragmento exacto ya detectado por
    `_PATRON_FECHA`) segun su formato y valida que dia/mes/anio formen
    una fecha real del calendario -- por ejemplo '31/04/2026' (abril
    solo tiene 30 dias) o '29/02/2026' (2026 no es bisiesto).

    Para el formato numerico con separador asume la convencion DD/MM/AAAA
    (la misma que usa el resto de esta herramienta y sus documentos de
    origen -- ver Documento Maestro). Esto NO resuelve la ambiguedad real
    DD/MM vs MM/DD para dias <= 12 (ambas lecturas serian fechas
    validas, no hay nada que advertir en ese caso); solo detecta
    combinaciones que son invalidas bajo cualquier lectura razonable de
    dia/mes (dia > 31, mes > 12, o el dia no existe en ese mes/anio)."""
    match = _PATRON_FECHA_NUMERICA.match(texto)
    if match:
        return _advertencia_fecha_invalida(int(match["dia"]), int(match["mes"]), _expandir_anio(match["anio"]))
    match = _PATRON_FECHA_ISO.match(texto)
    if match:
        return _advertencia_fecha_invalida(int(match["dia"]), int(match["mes"]), int(match["anio"]))
    match = _PATRON_FECHA_TEXTUAL.match(texto)
    if match:
        mes = _MESES_EN_ORDEN.index(match["mes"].lower()) + 1
        return _advertencia_fecha_invalida(int(match["dia"]), mes, int(match["anio"]))
    return None  # pragma: no cover -- todo texto ya vino de _PATRON_FECHA, siempre matchea uno de los tres.


def detectar_fechas_y_cifras(markdown: str) -> list[HallazgoVerificacion]:
    """Recorre `markdown` una sola vez por patron y devuelve todos los
    hallazgos ordenados por posicion (fechas y cifras intercaladas,
    en el mismo orden en que el revisor los va a encontrar leyendo de
    arriba a abajo)."""
    hallazgos: list[HallazgoVerificacion] = []
    for match in _PATRON_FECHA.finditer(markdown):
        texto = match.group(0)
        hallazgos.append(
            HallazgoVerificacion(
                tipo=TipoHallazgoVerificacion.FECHA,
                texto=texto,
                posicion=match.start(),
                advertencia=_advertencia_para_texto_de_fecha(texto),
            )
        )
    for match in _PATRON_CIFRA.finditer(markdown):
        hallazgos.append(
            HallazgoVerificacion(tipo=TipoHallazgoVerificacion.CIFRA, texto=match.group(0), posicion=match.start())
        )
    hallazgos.sort(key=lambda h: h.posicion)
    return hallazgos
