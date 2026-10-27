"""Entidades del contexto Pruebas de aceptacion (Fase 9 del orden
aprobado 2026-07-28; Documento Maestro, seccion 8.1 "Pruebas minimas por
dominio" y seccion 8.2 "Umbrales recomendados de liberacion").

A diferencia de `domain.reports` (Fase 8, documentacion recurrente que
un operador del proyecto puede querer generar en cualquier momento),
este contexto describe el resultado de UNA corrida de verificacion de
la HERRAMIENTA MISMA contra un corpus real de documentos
representativos (Anexo B del Documento Maestro, confirmado 2026-07-28:
"el usuario ya cuenta con archivos de prueba representativos"). No es
una funcionalidad que el usuario final del producto use en su dia a
dia -- es una actividad de control de calidad del propio desarrollo,
deliberadamente distinta de la suite de `pytest` de este codigo (que
verifica que el CODIGO funciona; esto verifica que la HERRAMIENTA
COMPLETA se comporta bien sobre documentos reales, no sinteticos).

Value objects puros, sin metodos de transicion de estado -- mismo
criterio que `domain.reports.entities`. `domain.acceptance` no importa
ningun otro paquete `domain.*`."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CriterioDominio(BaseModel):
    """Un renglon de la tabla "Pruebas minimas por dominio" (Documento
    Maestro, seccion 8.1), evaluado contra el corpus real de la corrida
    actual."""

    dominio: str
    """Uno de los siete de la tabla 8.1: 'Inventario', 'Extraccion',
    'OCR', 'Normalizacion', 'Markdown', 'Trazabilidad', 'Liberacion'."""
    descripcion: str
    """El texto de "Validaciones minimas" de esa fila, seccion 8.1."""
    cumplido: Optional[bool] = None
    """`True`/`False` si el corpus actual tenia al menos un archivo para
    ejercitar este dominio; `None` si el corpus todavia no cubre este
    dominio (por ejemplo, OCR sin ningun PDF escaneado todavia) --
    "pendiente por falta de corpus", nunca un `False` que sugeriria una
    falla real de la herramienta."""
    detalle: str = ""
    """Explicacion legible: que se evaluo, sobre que documentos, o por
    que quedo pendiente."""


class CriterioUmbral(BaseModel):
    """Un renglon de la tabla "Umbrales recomendados de liberacion"
    (Documento Maestro, seccion 8.2), evaluado sobre los documentos
    LIBERADO de la corrida actual."""

    indicador: str
    umbral_esperado: str
    valor_observado: str
    cumplido: bool


class InformeAceptacion(BaseModel):
    """Resultado completo de una corrida de pruebas de aceptacion sobre
    un corpus real (invocada por
    `scripts/ejecutar_pruebas_aceptacion.py`, nunca automaticamente)."""

    fecha: str
    """ISO 8601 del momento en que se ejecuto la corrida."""
    corpus_ruta: str
    documentos_evaluados: list[str] = Field(default_factory=list)
    """Nombres de archivo (no rutas completas) de cada documento del
    corpus procesado en esta corrida."""
    criterios_dominio: list[CriterioDominio] = Field(default_factory=list)
    criterios_umbral: list[CriterioUmbral] = Field(default_factory=list)

    def aprobado(self) -> bool:
        """`True` si ningun criterio evaluado (`cumplido is False`)
        fallo y todos los umbrales se cumplieron. Los dominios
        pendientes por falta de corpus (`cumplido is None`) no cuentan
        como falla -- ver `esta_completo()` para saber si, ademas,
        el corpus ya cubre los siete dominios."""
        dominio_ok = all(c.cumplido is not False for c in self.criterios_dominio)
        umbral_ok = all(c.cumplido for c in self.criterios_umbral)
        return dominio_ok and umbral_ok

    def esta_completo(self) -> bool:
        """`True` si NINGUN dominio quedo pendiente por falta de
        corpus. Un informe puede estar `aprobado()` (sin fallas reales)
        sin estar `esta_completo()` (todavia faltan archivos
        representativos para algunos dominios) -- son preguntas
        distintas a proposito."""
        return all(c.cumplido is not None for c in self.criterios_dominio)
