"""Reglas puras sobre rutas de archivo que deben dar el mismo resultado en
cualquier sistema operativo (auditoria 2026-09-30).

`pathlib.Path(ruta).name` solo reconoce el separador del sistema donde
corre el proceso: en macOS/Linux, `Path("C:\\x\\doc.md").name` devuelve la
cadena completa. El manifiesto (`GenerarManifiesto`) y la carpeta de
entrega (`LocalEntregaRagStudioStore`) deben derivar el MISMO nombre de
archivo de `Documento.ruta_markdown`; si no, la fila del manifiesto
apuntaria a un archivo con otro nombre."""
from __future__ import annotations

import re

_PATRON_SEPARADOR_RUTA = re.compile(r"[\\/]+")


def nombre_de_archivo_multiplataforma(ruta: str) -> str:
    """Ultimo segmento no vacio de `ruta`, reconociendo "/" y "\\" como
    separadores. Si `ruta` no tiene ningun separador, devuelve la misma
    cadena sin espacios en los extremos."""
    segmentos = [s for s in _PATRON_SEPARADOR_RUTA.split(ruta.strip()) if s]
    return segmentos[-1] if segmentos else ruta.strip()
