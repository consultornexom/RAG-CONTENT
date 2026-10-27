"""Adaptador de ManifestWriter sobre el sistema de archivos local
(ADR-001, seccion 4). Escribe el manifiesto de entrega hacia RAG STUDIO
(Modulo 12, Documento Maestro seccion 4.6.1) dentro de 12_exportaciones/
del proyecto, siempre con el mismo nombre de archivo -- cada llamada
sobrescribe la anterior, nunca acumula (seccion 4.11.1: "el
comportamiento es determinista").

Version 2 del esquema de manifiesto (2026-09-29, incidencia real de
portabilidad: un lote procesado en Windows se copio a un equipo macOS y
RAG STUDIO reporto "Importadas: 0 / Omitidas: 13" porque `ruta_archivo`
traia la ruta absoluta completa del equipo productor -- ver Documento
Maestro seccion 4.6.1 y CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md
para el analisis completo). Dos cambios respecto de la version anterior:

1. `FilaManifiesto.ruta_archivo` ahora es SOLO el nombre de archivo
   (ver `application.documents.commands.generar_manifiesto._fila_de`),
   nunca una ruta absoluta del equipo productor -- es relativa a la
   carpeta que contiene el propio manifiesto (`14_entrega_rag_studio/`
   o `12_exportaciones/`), nunca contiene "/" ni "\\".
2. Se agrega la columna `manifest_schema_version` (siempre "2" en
   manifiestos generados desde esta version) para que RAG STUDIO pueda
   distinguir manifiestos nuevos (contrato portable) de manifiestos
   legado (sin esta columna, generados antes de esta correccion, con
   `ruta_archivo` como ruta absoluta) sin ambiguedad. Se escribe aqui,
   en el adaptador de infraestructura, y no en `FilaManifiesto`
   (domain): es un detalle del formato de serializacion del CSV, no un
   dato del dominio de RAG Content Studio.

Version 1 (manifiestos generados por versiones anteriores de esta
herramienta, ya en manos de operadores) sigue siendo un formato valido
-- RAG STUDIO conserva un resolutor de compatibilidad para leerlos sin
que el operador tenga que editarlos a mano."""
from __future__ import annotations

import csv
from pathlib import Path

from domain.documents.entities import FilaManifiesto
from domain.documents.ports import ManifestWriter

VERSION_ESQUEMA_MANIFIESTO = "2"
"""Version del contrato de manifiesto que escribe esta version del
codigo (ver docstring del modulo). RAG STUDIO trata como "legado v1"
cualquier manifiesto cuyas filas no traigan esta columna."""

_COLUMNAS = (
    "manifest_schema_version",
    "titulo",
    "tipo_fuente",
    "ruta_archivo",
    "area_propietaria",
    "nivel_acceso",
    "idioma",
    "hash_contenido",
    "vigente_desde",
    "vigente_hasta",
    "autoridad_fuente",
    "sustituye_a",
)


class CsvManifestWriter(ManifestWriter):
    def __init__(self, carpeta_exportaciones: Path):
        self._carpeta_exportaciones = carpeta_exportaciones

    def escribir(self, filas: list[FilaManifiesto]) -> str:
        self._carpeta_exportaciones.mkdir(parents=True, exist_ok=True)
        ruta = self._carpeta_exportaciones / "manifiesto.csv"
        with ruta.open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=_COLUMNAS)
            escritor.writeheader()
            for fila in filas:
                valores = {columna: getattr(fila, columna) for columna in _COLUMNAS if columna != "manifest_schema_version"}
                valores["manifest_schema_version"] = VERSION_ESQUEMA_MANIFIESTO
                escritor.writerow({columna: valor if valor is not None else "" for columna, valor in valores.items()})
        return str(ruta)
