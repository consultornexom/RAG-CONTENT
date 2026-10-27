"""GenerarInformeTrazabilidad (Fase 8, Documento Maestro seccion 7.1)."""
from __future__ import annotations

from application.reports.commands.generar_informe_trazabilidad import GenerarInformeTrazabilidad
from domain.documents.entities import Aprobacion, Documento, FormatoDocumento
from domain.documents.ports import AprobacionRepository
from domain.reports.ports import ReportWriter
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "3" * 64


class _FakeAprobacionRepository(AprobacionRepository):
    def __init__(self, aprobaciones: list[Aprobacion] | None = None) -> None:
        self._aprobaciones = list(aprobaciones or [])

    def save(self, aprobacion: Aprobacion) -> None:
        self._aprobaciones.append(aprobacion)

    def list_by_document(self, documento_id: str):
        return [a for a in self._aprobaciones if a.documento_id == documento_id]


class _FakeReportWriter(ReportWriter):
    def __init__(self) -> None:
        self.filas = None

    def escribir_inventario(self, filas):
        raise NotImplementedError

    def escribir_procesamiento(self, filas):
        raise NotImplementedError

    def escribir_revision(self, filas):
        raise NotImplementedError

    def escribir_incidencias(self, filas):
        raise NotImplementedError

    def escribir_calidad(self, filas):
        raise NotImplementedError

    def escribir_trazabilidad(self, filas):
        self.filas = filas
        return "/tmp/informe_trazabilidad.csv"

    def escribir_acta_cierre_lote(self, acta):
        raise NotImplementedError


def _documento(documento_id: str) -> Documento:
    return Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH,
        tamano_bytes=1024,
    )


def test_documento_sin_aprobacion() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeTrazabilidad(_FakeDocumentRepository([_documento("doc-1")]), _FakeAprobacionRepository(), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.aprobador is None
    assert fila.fecha_aprobacion is None
    assert fila.hash_sha256 == _HASH


def test_documento_con_varias_aprobaciones_usa_la_mas_reciente() -> None:
    writer = _FakeReportWriter()
    primera = Aprobacion(documento_id="doc-1", aprobador="ana")
    segunda = Aprobacion(documento_id="doc-1", aprobador="luis")
    aprobacion_repo = _FakeAprobacionRepository([primera, segunda])
    caso_de_uso = GenerarInformeTrazabilidad(_FakeDocumentRepository([_documento("doc-1")]), aprobacion_repo, writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.aprobador == "luis"  # created_at mas reciente en la lista de creacion
