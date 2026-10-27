"""Autoguardado de avance del asistente por etapas (Fase 11.2,
Documento Maestro seccion 4.11.1: "las sesiones son recuperables ante
cierres inesperados -- autoguardado periodico de avance e
incidencias"). Las incidencias ya se persisten de verdad desde el
Modulo 10 (aplicacion.db/proyecto.db, sin cambios); lo unico que faltaba
persistir era "en que etapa del asistente se quedo el operador" para
cada proyecto -- algo puramente de presentacion (no es una regla de
negocio, no vive en ningun servicio de application, por eso no rompe
ADR-001 seccion 4 que esto viva directo en `ui`). Un archivo JSON chico
dentro de la propia carpeta del proyecto, mismo criterio de "todo lo
del proyecto viaja con su carpeta" que ya usa el resto de la
herramienta (respaldos en 13_respaldos/, reportes en 10_reportes/,
etc.). Se guarda en cada cambio de etapa -- para un flujo guiado y
lineal, el avance solo cambia al cambiar de etapa, asi que guardar en
ese momento ya cumple "periodico" sin necesitar un QTimer real."""
from __future__ import annotations

import json
from pathlib import Path

_NOMBRE_ARCHIVO = ".asistente_estado.json"


def leer_etapa(ruta_carpeta_proyecto: str) -> int:
    """Devuelve la etapa guardada para este proyecto, o 0 (la primera)
    si nunca se guardo nada o el archivo esta corrupto/ilegible --
    nunca lanza, el autoguardado es una comodidad, no una fuente de
    verdad critica."""
    ruta = Path(ruta_carpeta_proyecto) / _NOMBRE_ARCHIVO
    if not ruta.exists():
        return 0
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return int(datos.get("etapa", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        # Auditoria 2026-08-24: un archivo con JSON VALIDO que no es un
        # objeto (por ejemplo "[1,2,3]", "5" o "null" -- plausible ante
        # una escritura parcial/carrera, o una edicion manual del
        # archivo) hacia que `json.loads` no lanzara pero `datos.get(...)`
        # si, con `AttributeError`/`TypeError` segun el tipo, fuera de la
        # tupla que se capturaba -- rompiendo el "nunca lanza" que
        # promete este docstring, propagado sin capturar hasta el slot
        # de Qt que abre el proyecto (`AsistenteWidget.establecer_proyecto`).
        return 0


def guardar_etapa(ruta_carpeta_proyecto: str, etapa: int) -> None:
    ruta = Path(ruta_carpeta_proyecto) / _NOMBRE_ARCHIVO
    try:
        ruta.write_text(json.dumps({"etapa": etapa}), encoding="utf-8")
    except OSError:
        pass  # ver docstring del modulo: nunca debe romper el flujo del asistente.
