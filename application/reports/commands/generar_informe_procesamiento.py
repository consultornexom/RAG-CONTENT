"""Caso de uso de Fase 8: "Informe de procesamiento" (Documento Maestro,
seccion 7.1: "Extracciones, OCR, audio, errores, reintentos y
herramientas utilizadas").

Depende directamente de `domain.jobs.ports.TrabajoRepository` (Fase 6) --
mismo patron de acoplamiento cruzado que `GenerarManifiesto` con
`VigenciaRepository`. Solo mira los trabajos de tipo EXTRACCION: es la
unica etapa pesada que puede fallar por causas de OCR/audio (Modulo 6/7,
ver el docstring de `domain.jobs.entities.TipoTrabajo`), que es
justamente lo que este informe reporta.

Corregido 2026-07-31 (comentario real del consultor, tras analizar una
corrida completa de un proyecto real): la columna 'advertencias' solo
mostraba una cantidad ("1"), sin decir cual era -- quien audita la
calidad de un documento tenia que ir a buscar el texto real a otro lado
(o no podia, si no tenia acceso al codigo). Ahora lleva el texto
completo de cada advertencia (ver `FilaProcesamiento.advertencias`)."""
from __future__ import annotations

from domain.documents.entities import Documento, TipoProcesamiento
from domain.documents.ports import DocumentRepository
from domain.jobs.entities import TipoTrabajo, Trabajo
from domain.jobs.ports import TrabajoRepository
from domain.reports.entities import FilaProcesamiento
from domain.reports.ports import ReportWriter

_HERRAMIENTA_POR_TIPO: dict[TipoProcesamiento, str] = {
    TipoProcesamiento.EXTRACCION_DIRECTA: "Extraccion directa (pypdf/docx/openpyxl/csv/txt/json segun formato)",
    TipoProcesamiento.OCR: "Tesseract (pytesseract)",
    TipoProcesamiento.TRANSCRIPCION: "faster-whisper (Whisper local)",
    TipoProcesamiento.CORRECCION_MANUAL: "Manual (sin herramienta automatica)",
}
"""Mapeo de presentacion, no una regla de negocio -- ver
`domain.documents.entities.TipoProcesamiento` para el vocabulario real
que asigna el Modulo 4."""


def _fila_de(documento: Documento, trabajo_repository: TrabajoRepository) -> FilaProcesamiento:
    trabajos_extraccion: list[Trabajo] = [
        t for t in trabajo_repository.list_by_document(documento.id) if t.tipo == TipoTrabajo.EXTRACCION
    ]
    if trabajos_extraccion:
        mas_reciente = max(trabajos_extraccion, key=lambda t: t.actualizado_en)
        intentos_trabajo = sum(t.intentos for t in trabajos_extraccion)
        estado_trabajo = mas_reciente.estado.value
    else:
        intentos_trabajo = 0
        estado_trabajo = "sin_trabajo_asociado"

    tipo_procesamiento = documento.tipo_procesamiento
    return FilaProcesamiento(
        documento_id=documento.id,
        tipo_procesamiento=tipo_procesamiento.value if tipo_procesamiento is not None else "sin_clasificar",
        herramienta=_HERRAMIENTA_POR_TIPO.get(tipo_procesamiento, "sin_clasificar") if tipo_procesamiento else "N/D",
        advertencias=documento.advertencias_extraccion,
        intentos_trabajo=intentos_trabajo,
        estado_trabajo=estado_trabajo,
    )


class GenerarInformeProcesamiento:
    def __init__(
        self, document_repository: DocumentRepository, trabajo_repository: TrabajoRepository, writer: ReportWriter
    ):
        self._document_repository = document_repository
        self._trabajo_repository = trabajo_repository
        self._writer = writer

    def execute(self) -> str:
        """Devuelve la ruta absoluta del informe escrito. Incluye todos
        los documentos del proyecto que ya se clasificaron (Modulo 4) o
        despues -- los que siguen RECIBIDO/INVENTARIADO todavia no
        tienen nada que procesar, pero se incluyen igual con
        'sin_clasificar' para que el informe siga siendo un inventario
        completo, mismo criterio que el informe de inventario."""
        filas = [_fila_de(d, self._trabajo_repository) for d in self._document_repository.list()]
        return self._writer.escribir_procesamiento(filas)
