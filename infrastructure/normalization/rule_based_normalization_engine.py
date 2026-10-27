"""Motor de reglas propio del Modulo 9 (Documento Maestro, seccion 4.6:
"aplicar reglas sin alterar silenciosamente"). RAG STUDIO no tiene este
adaptador (no normaliza Markdown ya extraido); es propio de RAG Content
Studio Desktop.

Catalogo de tipo_regla reconocidos en esta primera version -- cubre las
capacidades esenciales del Modulo 9 mas concretas y deterministas
(encabezados/pies repetidos, saltos de linea, acronimos/glosario, datos
sensibles, espacios en celdas de tabla); parrafos/titulos/listas ya
quedan normalizados como Markdown real desde el Modulo 5 (extractores),
asi que este motor no repite ese trabajo:

- 'eliminar_linea_repetida': quita cada linea exactamente igual al
  parametro 'texto' (encabezados/pies de pagina que RAG STUDIO no
  interpreta pero que ensucian el cuerpo del documento).
- 'colapsar_saltos_de_linea': reduce 3+ saltos de linea consecutivos a
  exactamente 2 (un parrafo Markdown estandar).
- 'expandir_acronimo': en la primera aparicion de la palabra completa
  del parametro 'acronimo', la reemplaza por 'expansion (acronimo)' --
  las apariciones siguientes quedan igual (glosario aplicado una vez).
- 'redactar_patron': sustituye cada coincidencia de la expresion
  regular del parametro 'patron' por '[DATO SENSIBLE REDACTADO]'.
- 'normalizar_espacios_en_tablas': recorta espacios sobrantes dentro de
  cada celda de una fila de tabla Markdown ('| ... |').

Cada regla que produce un cambio real lo registra en
ResultadoNormalizacion.cambios -- una regla sin efecto sobre este
documento en particular no es un error, simplemente no agrega nada.
"""
from __future__ import annotations

import re

from domain.documents.entities import ResultadoNormalizacion
from domain.documents.exceptions import ReglaNormalizacionDesconocidaError
from domain.documents.ports import NormalizationEngine
from domain.profiles.entities import ReglaNormalizacion

_PATRON_SALTOS_EXCESIVOS = re.compile(r"\n{3,}")
_PATRON_FILA_TABLA = re.compile(r"^\|.*\|$")


def _eliminar_linea_repetida(markdown: str, parametros: dict[str, str]) -> tuple[str, str | None]:
    texto = parametros.get("texto", "")
    if not texto:
        return markdown, None
    lineas = markdown.split("\n")
    filtradas = [linea for linea in lineas if linea.strip() != texto.strip()]
    eliminadas = len(lineas) - len(filtradas)
    if eliminadas == 0:
        return markdown, None
    cambio = f"Se eliminaron {eliminadas} linea(s) repetida(s): {texto!r}."
    return "\n".join(filtradas), cambio


def _colapsar_saltos_de_linea(markdown: str, parametros: dict[str, str]) -> tuple[str, str | None]:
    nuevo = _PATRON_SALTOS_EXCESIVOS.sub("\n\n", markdown)
    if nuevo == markdown:
        return markdown, None
    return nuevo, "Se colapsaron saltos de linea excesivos (3 o mas consecutivos) a un solo parrafo."


def _expandir_acronimo(markdown: str, parametros: dict[str, str]) -> tuple[str, str | None]:
    acronimo = parametros.get("acronimo", "")
    expansion = parametros.get("expansion", "")
    if not acronimo or not expansion:
        return markdown, None
    patron = re.compile(rf"\b{re.escape(acronimo)}\b")
    if not patron.search(markdown):
        return markdown, None
    nuevo = patron.sub(f"{expansion} ({acronimo})", markdown, count=1)
    return nuevo, f"Se expandio la primera aparicion de {acronimo!r} a {expansion!r}."


def _redactar_patron(markdown: str, parametros: dict[str, str]) -> tuple[str, str | None]:
    patron_texto = parametros.get("patron", "")
    if not patron_texto:
        return markdown, None
    try:
        patron = re.compile(patron_texto)
    except re.error as exc:
        raise ReglaNormalizacionDesconocidaError(f"redactar_patron con patron invalido {patron_texto!r}: {exc}") from exc
    nuevo, cantidad = patron.subn("[DATO SENSIBLE REDACTADO]", markdown)
    if cantidad == 0:
        return markdown, None
    descripcion = parametros.get("descripcion", patron_texto)
    return nuevo, f"Se redactaron {cantidad} coincidencia(s) del patron {descripcion!r}."


def _normalizar_espacios_en_tablas(markdown: str, parametros: dict[str, str]) -> tuple[str, str | None]:
    lineas = markdown.split("\n")
    celdas_normalizadas = 0
    resultado: list[str] = []
    for linea in lineas:
        if not _PATRON_FILA_TABLA.match(linea.strip()):
            resultado.append(linea)
            continue
        celdas = linea.strip().strip("|").split("|")
        celdas_recortadas = [c.strip() for c in celdas]
        celdas_normalizadas += sum(
            1 for antes, despues in zip(celdas, celdas_recortadas, strict=True) if antes != despues
        )
        resultado.append("| " + " | ".join(celdas_recortadas) + " |")
    nuevo = "\n".join(resultado)
    if nuevo == markdown:
        return markdown, None
    return nuevo, f"Se normalizaron espacios en {celdas_normalizadas} celda(s) de tabla."


_MANEJADORES = {
    "eliminar_linea_repetida": _eliminar_linea_repetida,
    "colapsar_saltos_de_linea": _colapsar_saltos_de_linea,
    "expandir_acronimo": _expandir_acronimo,
    "redactar_patron": _redactar_patron,
    "normalizar_espacios_en_tablas": _normalizar_espacios_en_tablas,
}


class RuleBasedNormalizationEngine(NormalizationEngine):
    def normalizar(self, markdown: str, reglas: list[ReglaNormalizacion]) -> ResultadoNormalizacion:
        cambios: list[str] = []
        for regla in reglas:
            manejador = _MANEJADORES.get(regla.tipo_regla)
            if manejador is None:
                raise ReglaNormalizacionDesconocidaError(regla.tipo_regla)
            markdown, cambio = manejador(markdown, regla.parametros)
            if cambio is not None:
                cambios.append(cambio)
        return ResultadoNormalizacion(markdown_normalizado=markdown, cambios=cambios)
