"""Adaptador de ReportWriter sobre el sistema de archivos local (ADR-001,
seccion 4). Escribe los siete documentos de la seccion 7.1 del Documento
Maestro dentro de 10_reportes/ del proyecto: los seis informes
tabulares en CSV (mismo formato y criterio que
`infrastructure.filesystem.csv_manifest_writer.CsvManifestWriter` --
siempre el mismo nombre de archivo, sobrescribiendo la version anterior)
y el acta de cierre de lote en Markdown (un archivo por lote, porque
puede haber varias actas vivas a la vez).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from domain.reports.entities import (
    ActaCierreLote,
    FilaCalidad,
    FilaIncidencia,
    FilaInventario,
    FilaProcesamiento,
    FilaRevision,
    FilaTrazabilidad,
)
from domain.reports.ports import ReportWriter

_COLUMNAS_INVENTARIO = ("documento_id", "nombre_original", "formato", "area_propietaria", "prioridad", "criticidad", "estado", "vigencia")
_COLUMNAS_PROCESAMIENTO = ("documento_id", "tipo_procesamiento", "herramienta", "advertencias", "intentos_trabajo", "estado_trabajo")
_COLUMNAS_REVISION = ("documento_id", "revisor", "fecha", "incidencias_detectadas", "comentario")
_COLUMNAS_INCIDENCIAS = ("incidencia_id", "documento_id", "etapa", "tipo", "severidad", "estado", "responsable", "abierta", "vencida")
_COLUMNAS_CALIDAD = ("documento_id", "estado", "advertencias_extraccion", "advertencias_markdown", "incumplimientos", "semaforo")
_COLUMNAS_TRAZABILIDAD = (
    "documento_id",
    "nombre_original",
    "hash_sha256",
    "ruta_extraccion",
    "ruta_normalizado",
    "ruta_markdown",
    "hash_markdown",
    "aprobador",
    "fecha_aprobacion",
)


def _valor_csv(valor: Any) -> str:
    """Serializa un valor de una Fila a texto de celda CSV: `None` ->
    cadena vacia (mismo criterio que `CsvManifestWriter`), `bool` ->
    'si'/'no' (columnas en espanol, seccion 4.11.1: sin tecnicismos
    crudos), `list` -> valores unidos con '; '."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "si" if valor else "no"
    if isinstance(valor, list):
        return "; ".join(str(v) for v in valor)
    return str(valor)


def _escribir_csv(ruta: Path, columnas: tuple[str, ...], filas: list[Any]) -> str:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({columna: _valor_csv(getattr(fila, columna)) for columna in columnas})
    return str(ruta)


def _lista_o_ninguno(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "(ninguno)"


class LocalReportWriter(ReportWriter):
    def __init__(self, carpeta_reportes: Path):
        self._carpeta_reportes = carpeta_reportes

    def escribir_inventario(self, filas: list[FilaInventario]) -> str:
        return _escribir_csv(self._carpeta_reportes / "informe_inventario.csv", _COLUMNAS_INVENTARIO, filas)

    def escribir_procesamiento(self, filas: list[FilaProcesamiento]) -> str:
        return _escribir_csv(self._carpeta_reportes / "informe_procesamiento.csv", _COLUMNAS_PROCESAMIENTO, filas)

    def escribir_revision(self, filas: list[FilaRevision]) -> str:
        return _escribir_csv(self._carpeta_reportes / "informe_revision.csv", _COLUMNAS_REVISION, filas)

    def escribir_incidencias(self, filas: list[FilaIncidencia]) -> str:
        return _escribir_csv(self._carpeta_reportes / "informe_incidencias.csv", _COLUMNAS_INCIDENCIAS, filas)

    def escribir_calidad(self, filas: list[FilaCalidad]) -> str:
        return _escribir_csv(self._carpeta_reportes / "informe_calidad.csv", _COLUMNAS_CALIDAD, filas)

    def escribir_trazabilidad(self, filas: list[FilaTrazabilidad]) -> str:
        return _escribir_csv(self._carpeta_reportes / "informe_trazabilidad.csv", _COLUMNAS_TRAZABILIDAD, filas)

    def escribir_acta_cierre_lote(self, acta: ActaCierreLote) -> str:
        self._carpeta_reportes.mkdir(parents=True, exist_ok=True)
        ruta = self._carpeta_reportes / f"acta_cierre_lote_{acta.lote_id}.md"
        contenido = (
            "# Acta de cierre de lote\n\n"
            f"**Lote:** {acta.nombre_lote} (`{acta.lote_id}`)\n"
            f"**Fecha de cierre:** {acta.fecha_cierre or 'N/D'}\n"
            f"**Version del acta:** {acta.version}\n\n"
            f"## Documentos liberados ({len(acta.liberados)})\n\n{_lista_o_ninguno(acta.liberados)}\n\n"
            f"## Documentos bloqueados ({len(acta.bloqueados)})\n\n{_lista_o_ninguno(acta.bloqueados)}\n\n"
            f"## Exclusiones ({len(acta.exclusiones)})\n\n{_lista_o_ninguno(acta.exclusiones)}\n\n"
            f"## Riesgos identificados\n\n{_lista_o_ninguno(acta.riesgos)}\n\n"
            f"## Aprobadores\n\n{_lista_o_ninguno(acta.aprobadores)}\n"
        )
        ruta.write_text(contenido, encoding="utf-8")
        return str(ruta)
