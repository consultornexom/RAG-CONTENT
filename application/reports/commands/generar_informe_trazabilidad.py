"""Caso de uso de Fase 8: "Informe de trazabilidad" (Documento Maestro,
seccion 7.1: "Original, hash, extraccion, normalizacion, Markdown y
aprobaciones"). Incluye todos los documentos del proyecto -- la
trazabilidad completa (seccion 4.1) no se limita a los ya LIBERADO."""
from __future__ import annotations

from domain.documents.entities import Aprobacion, Documento
from domain.documents.ports import AprobacionRepository, DocumentRepository
from domain.reports.entities import FilaTrazabilidad
from domain.reports.ports import ReportWriter


def _aprobacion_mas_reciente(aprobaciones: list[Aprobacion]) -> Aprobacion | None:
    return max(aprobaciones, key=lambda a: a.fecha) if aprobaciones else None


def _fila_de(documento: Documento, aprobacion_repository: AprobacionRepository) -> FilaTrazabilidad:
    aprobacion = _aprobacion_mas_reciente(aprobacion_repository.list_by_document(documento.id))
    return FilaTrazabilidad(
        documento_id=documento.id,
        nombre_original=documento.nombre_original,
        hash_sha256=documento.hash_sha256,
        ruta_extraccion=documento.ruta_extraccion,
        ruta_normalizado=documento.ruta_normalizado,
        ruta_markdown=documento.ruta_markdown,
        hash_markdown=documento.hash_markdown,
        aprobador=aprobacion.aprobador if aprobacion else None,
        fecha_aprobacion=aprobacion.fecha.isoformat() if aprobacion else None,
    )


class GenerarInformeTrazabilidad:
    def __init__(
        self, document_repository: DocumentRepository, aprobacion_repository: AprobacionRepository, writer: ReportWriter
    ):
        self._document_repository = document_repository
        self._aprobacion_repository = aprobacion_repository
        self._writer = writer

    def execute(self) -> str:
        """Devuelve la ruta absoluta del informe escrito."""
        filas = [_fila_de(d, self._aprobacion_repository) for d in self._document_repository.list()]
        return self._writer.escribir_trazabilidad(filas)
