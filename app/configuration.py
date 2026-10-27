"""Rutas de la aplicacion (Documento Maestro, seccion 4.1: ruta raiz
unica). Ningun otro modulo debe construir estas rutas por su cuenta --
siempre a traves de esta configuracion, para que un cambio de raiz se
haga en un solo lugar.

Bug real encontrado 2026-07-30: hasta esta fecha, la raiz por defecto
era una constante hardcodeada con una ruta absoluta de Linux
("/media/disco/Data/RAG CONTENT STUDIO", el disco del consultor) --
funcionaba bien mientras la unica maquina real que corria la
aplicacion era esa, pero un usuario probando la herramienta en Windows
termino con un proyecto creado en un lugar inesperado: Windows
interpreta una cadena que empieza con "/" como una ruta relativa a la
raiz de la unidad de trabajo actual, no como la ruta Linux literal, asi
que la carpeta terminaba viviendo en un sitio no obvio para el usuario
(ADR-001, seccion 11, ya habia senalado este riesgo exacto como
pendiente de resolver "antes de probar en Windows/macOS"). Corregido
resolviendo la raiz en tres pasos, en este orden (ver cargar_rutas()):
1) argumento explicito `raiz` (como ya existia, solo para pruebas);
2) variable de entorno RAG_CONTENT_STUDIO_ROOT, si esta definida --
mecanismo para que una instalacion existente conserve su carpeta actual
sin tener que mover nada (ver MANUAL_OPERACION.md); 3) si ninguna de las
dos anteriores aplica, una carpeta dentro del home del usuario
(`Path.home()`), calculada en tiempo de ejecucion con pathlib -- nunca
una cadena fija en el codigo fuente, para que el mismo codigo funcione
igual en Windows, macOS y Linux sin ninguna rama por sistema operativo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_VARIABLE_ENTORNO_RAIZ = "RAG_CONTENT_STUDIO_ROOT"
"""Nombre de la variable de entorno que permite fijar la raiz sin tocar
el codigo -- pensada tanto para una instalacion existente (ver bug de
2026-07-30 arriba) como para quien quiera correr la herramienta contra
una carpeta distinta a la de su usuario del sistema operativo (por
ejemplo, un disco de red compartido)."""

_NOMBRE_CARPETA_POR_DEFECTO = "RAG Content Studio Desktop"
"""Nombre de la subcarpeta dentro del home del usuario que se usa
cuando no hay `raiz` explicito ni RAG_CONTENT_STUDIO_ROOT definida --
mismo nombre en los tres sistemas operativos soportados, para que sea
facil de encontrar sin tener que buscar documentacion."""


@dataclass(frozen=True)
class RutasAplicacion:
    raiz: Path

    @property
    def aplicacion_db(self) -> Path:
        return self.raiz / "aplicacion.db"

    @property
    def perfiles(self) -> Path:
        return self.raiz / "perfiles"

    @property
    def proyectos(self) -> Path:
        return self.raiz / "proyectos"

    @property
    def logs(self) -> Path:
        return self.raiz / "logs"


def cargar_rutas(raiz: str | os.PathLike[str] | None = None) -> RutasAplicacion:
    """Resuelve la ruta raiz unica (Documento Maestro, seccion 4.1) en
    tres pasos, en orden -- ver el bug de 2026-07-30 documentado arriba:

    1. `raiz` explicito (solo lo pasan las pruebas, ver tests/smoke).
    2. La variable de entorno RAG_CONTENT_STUDIO_ROOT, si esta definida.
    3. `Path.home() / "RAG Content Studio Desktop"` -- default
       multiplataforma, sin ninguna ruta fija en el codigo fuente."""
    if raiz is not None:
        base = Path(raiz)
    else:
        override = os.environ.get(_VARIABLE_ENTORNO_RAIZ)
        base = Path(override) if override else Path.home() / _NOMBRE_CARPETA_POR_DEFECTO
    return RutasAplicacion(raiz=base)
