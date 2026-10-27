"""GenerarInformeInventario (Fase 8, Documento Maestro seccion 7.1)."""
from __future__ import annotations

from datetime import date

from application.reports.commands.generar_informe_inventario import GenerarInformeInventario
from domain.documents.entities import Criticidad, Documento, FormatoDocumento, Prioridad
from domain.reports.entities import FilaInventario
from domain.reports.ports import ReportWriter
from domain.validity.entities import Vigencia
from domain.validity.ports import VigenciaRepository
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "1" * 64


class _FakeVigenciaRepository(VigenciaRepository):
    def __init__(self, vigencias: dict[str, Vigencia] | None = None) -> None:
        self._por_documento = vigencias or {}

    def save(self, vigencia: Vigencia) -> None:
        self._por_documento[vigencia.documento_id] = vigencia

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeReportWriter(ReportWriter):
    def __init__(self) -> None:
        self.filas_inventario: list[FilaInventario] = []

    def escribir_inventario(self, filas):
        self.filas_inventario = filas
        return "/tmp/informe_inventario.csv"

    def escribir_procesamiento(self, filas):
        raise NotImplementedError

    def escribir_revision(self, filas):
        raise NotImplementedError

    def escribir_incidencias(self, filas):
        raise NotImplementedError

    def escribir_calidad(self, filas):
        raise NotImplementedError

    def escribir_trazabilidad(self, filas):
        raise NotImplementedError

    def escribir_acta_cierre_lote(self, acta):
        raise NotImplementedError


def _documento(documento_id: str, **overrides) -> Documento:
    datos = {
        "id": documento_id,
        "proyecto_id": "PROY-0001",
        "nombre_original": "politica.pdf",
        "formato": FormatoDocumento.PDF,
        "ruta_origen": "/tmp/x/politica.pdf",
        "ruta_copia_original": "/proyecto/01_originales/abc_politica.pdf",
        "hash_sha256": _HASH,
        "tamano_bytes": 1024,
        "metadatos": {"area_propietaria": "rh"},
    }
    datos.update(overrides)
    return Documento(**datos)


def test_documento_sin_vigencia_registrada_es_desconocida() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeInventario(_FakeDocumentRepository([_documento("doc-1")]), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    assert writer.filas_inventario[0].vigencia == "desconocida"
    assert writer.filas_inventario[0].area_propietaria == "rh"


def test_documento_con_vigencia_sin_vencimiento() -> None:
    vigencia = Vigencia(documento_id="doc-1", vigente_desde=date(2020, 1, 1), sin_vencimiento=True, autoridad="RH")
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeInventario(
        _FakeDocumentRepository([_documento("doc-1")]), _FakeVigenciaRepository({"doc-1": vigencia}), writer
    )

    caso_de_uso.execute()

    assert writer.filas_inventario[0].vigencia == "sin_vencimiento"


def test_documento_con_vigencia_vencida() -> None:
    vigencia = Vigencia(
        documento_id="doc-1", vigente_desde=date(2000, 1, 1), vigente_hasta=date(2001, 1, 1), autoridad="RH"
    )
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeInventario(
        _FakeDocumentRepository([_documento("doc-1")]), _FakeVigenciaRepository({"doc-1": vigencia}), writer
    )

    caso_de_uso.execute()

    assert writer.filas_inventario[0].vigencia == "vencida"


def test_documento_con_vigencia_vigente() -> None:
    vigencia = Vigencia(
        documento_id="doc-1", vigente_desde=date(2000, 1, 1), vigente_hasta=date(2100, 1, 1), autoridad="RH"
    )
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeInventario(
        _FakeDocumentRepository([_documento("doc-1")]), _FakeVigenciaRepository({"doc-1": vigencia}), writer
    )

    caso_de_uso.execute()

    assert writer.filas_inventario[0].vigencia == "vigente"


def test_incluye_prioridad_criticidad_y_estado() -> None:
    writer = _FakeReportWriter()
    documento = _documento("doc-1", prioridad=Prioridad.ALTA, criticidad=Criticidad.CRITICO)
    caso_de_uso = GenerarInformeInventario(_FakeDocumentRepository([documento]), _FakeVigenciaRepository(), writer)

    caso_de_uso.execute()

    fila = writer.filas_inventario[0]
    assert fila.prioridad == "alta"
    assert fila.criticidad == "critico"
    assert fila.estado == "recibido"


def test_devuelve_la_ruta_del_writer() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeInventario(_FakeDocumentRepository(), _FakeVigenciaRepository(), writer)
    assert caso_de_uso.execute() == "/tmp/informe_inventario.csv"
