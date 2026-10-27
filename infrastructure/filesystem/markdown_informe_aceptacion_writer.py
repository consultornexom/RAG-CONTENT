"""Adaptador de InformeAceptacionWriter sobre el sistema de archivos
local (ADR-001, seccion 4). A diferencia de `LocalReportWriter` (Fase 8,
sobrescribe siempre el mismo archivo), cada corrida de aceptacion queda
archivada por separado dentro de `corpus_aceptacion/informes/` -- el
nombre del archivo incluye la fecha de la corrida."""
from __future__ import annotations

import re
from pathlib import Path

from domain.acceptance.entities import CriterioDominio, CriterioUmbral, InformeAceptacion
from domain.acceptance.ports import InformeAceptacionWriter

_PATRON_NO_ALFANUMERICO = re.compile(r"[^0-9A-Za-z_-]+")


def _nombre_archivo(fecha: str) -> str:
    return f"informe_aceptacion_{_PATRON_NO_ALFANUMERICO.sub('_', fecha)}.md"


def _marca(cumplido: bool | None) -> str:
    if cumplido is None:
        return "PENDIENTE"
    return "CUMPLE" if cumplido else "FALLA"


def _seccion_dominio(criterio: CriterioDominio) -> str:
    return f"### {criterio.dominio} -- {_marca(criterio.cumplido)}\n\n{criterio.descripcion}\n\n{criterio.detalle}\n"


def _fila_umbral(criterio: CriterioUmbral) -> str:
    return f"| {criterio.indicador} | {criterio.umbral_esperado} | {criterio.valor_observado} | {_marca(criterio.cumplido)} |"


class MarkdownInformeAceptacionWriter(InformeAceptacionWriter):
    def __init__(self, carpeta_informes: Path):
        self._carpeta_informes = carpeta_informes

    def escribir(self, informe: InformeAceptacion) -> str:
        self._carpeta_informes.mkdir(parents=True, exist_ok=True)
        ruta = self._carpeta_informes / _nombre_archivo(informe.fecha)

        secciones_dominio = "\n".join(_seccion_dominio(c) for c in informe.criterios_dominio)
        filas_umbral = "\n".join(_fila_umbral(c) for c in informe.criterios_umbral) or "| (sin datos) | | | |"
        documentos = "\n".join(f"- {nombre}" for nombre in informe.documentos_evaluados) or "(ninguno)"

        estado_general = "APROBADO" if informe.aprobado() else "CON HALLAZGOS"
        completo = "si" if informe.esta_completo() else "no (corpus incompleto para algunos dominios de la seccion 8.1)"

        contenido = (
            "# Informe de pruebas de aceptacion\n\n"
            f"**Fecha:** {informe.fecha}\n\n"
            f"**Corpus:** {informe.corpus_ruta}\n\n"
            f"**Resultado general:** {estado_general}\n\n"
            f"**Corpus completo (los 7 dominios de la seccion 8.1 cubiertos):** {completo}\n\n"
            f"## Documentos evaluados ({len(informe.documentos_evaluados)})\n\n{documentos}\n\n"
            f"## Pruebas minimas por dominio (Documento Maestro, seccion 8.1)\n\n{secciones_dominio}\n\n"
            "## Umbrales recomendados de liberacion (Documento Maestro, seccion 8.2)\n\n"
            "| Indicador | Umbral | Observado | Resultado |\n"
            "| --- | --- | --- | --- |\n"
            f"{filas_umbral}\n"
        )
        ruta.write_text(contenido, encoding="utf-8")
        return str(ruta)
