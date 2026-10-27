"""Caso de uso de Fase 8: "Informe de calidad" (Documento Maestro,
seccion 7.1: "Validaciones, incumplimientos, bloqueos y semaforo").

Depende directamente de `application.governance.service.
GovernanceService.verificar_documento_liberable()` -- reutiliza la MISMA
regla que `LiberarDocumento`/`CerrarLote` ya aplican, en vez de
duplicarla (mismo principio que `CerrarLote` reutilizandola en Fase 7).
`GovernanceService` es una fachada de aplicacion, no un puerto de
domain, pero ya es un precedente establecido para reutilizar reglas de
gobernanza entre contextos (ver el docstring de `CerrarLote`).

Corregido 2026-07-31 (comentario real del consultor, tras analizar una
corrida completa de un proyecto real): las columnas 'advertencias_*'
solo mostraban una cantidad ("1"), sin decir cual era -- confirmado con
un caso real: un documento OCR con advertencias_markdown=1 y
semaforo='verde' (LIBERADO), sin ninguna forma de saber, desde el
informe, que la advertencia real era "el Markdown final no tiene ningun
encabezado ni tabla real" (justo el sintoma del bug de tablas OCR
corregido antes ese mismo dia). Ahora llevan el texto completo de cada
advertencia (ver `FilaCalidad.advertencias_extraccion`/
`advertencias_markdown`)."""
from __future__ import annotations

from application.governance.service import GovernanceService
from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.ports import DocumentRepository
from domain.governance.exceptions import AprobacionFaltanteError, FuenteFaltanteError
from domain.reports.entities import FilaCalidad
from domain.reports.ports import ReportWriter

_ESTADOS_ROJO = frozenset({EstadoDocumento.BLOQUEADO, EstadoDocumento.DESCARTADO, EstadoDocumento.OBSOLETO})


def _calcular_semaforo(estado: EstadoDocumento, incumplimientos: list[str]) -> str:
    """Criterio del semaforo: 'verde' si esta LIBERADO o en flujo sin
    incumplimientos detectables todavia; 'amarillo' si esta en flujo
    pero incumpliria la liberacion hoy; 'rojo' si ya se resolvio de
    forma negativa (BLOQUEADO/DESCARTADO/OBSOLETO)."""
    if estado == EstadoDocumento.LIBERADO:
        return "verde"
    if estado in _ESTADOS_ROJO:
        return "rojo"
    return "amarillo" if incumplimientos else "verde"


def _incumplimientos_de(documento: Documento, governance: GovernanceService) -> list[str]:
    if documento.estado == EstadoDocumento.LIBERADO:
        # Garantizado por construccion: no se llega a LIBERADO sin haber
        # pasado esta misma verificacion (ver Documento.liberar()).
        return []
    try:
        governance.verificar_documento_liberable(documento.id)
    except (FuenteFaltanteError, AprobacionFaltanteError) as exc:
        return [str(exc)]
    return []


def _fila_de(documento: Documento, governance: GovernanceService) -> FilaCalidad:
    incumplimientos = _incumplimientos_de(documento, governance)
    return FilaCalidad(
        documento_id=documento.id,
        estado=documento.estado.value,
        advertencias_extraccion=documento.advertencias_extraccion,
        advertencias_markdown=documento.advertencias_markdown,
        incumplimientos=incumplimientos,
        semaforo=_calcular_semaforo(documento.estado, incumplimientos),
    )


class GenerarInformeCalidad:
    def __init__(self, document_repository: DocumentRepository, governance: GovernanceService, writer: ReportWriter):
        self._document_repository = document_repository
        self._governance = governance
        self._writer = writer

    def execute(self) -> str:
        """Devuelve la ruta absoluta del informe escrito."""
        filas = [_fila_de(d, self._governance) for d in self._document_repository.list()]
        return self._writer.escribir_calidad(filas)
