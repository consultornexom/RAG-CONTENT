"""GenerarInformeProcesamiento (Fase 8, Documento Maestro seccion 7.1)."""
from __future__ import annotations

from application.reports.commands.generar_informe_procesamiento import GenerarInformeProcesamiento
from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.jobs.entities import EstadoTrabajo, Trabajo, TipoTrabajo
from domain.jobs.ports import TrabajoRepository
from domain.reports.ports import ReportWriter
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "1" * 64


class _FakeTrabajoRepository(TrabajoRepository):
    def __init__(self, trabajos: list[Trabajo] | None = None) -> None:
        self._trabajos = list(trabajos or [])

    def save(self, trabajo: Trabajo) -> None:
        self._trabajos = [t for t in self._trabajos if t.id != trabajo.id] + [trabajo]

    def get(self, trabajo_id: str):
        return next((t for t in self._trabajos if t.id == trabajo_id), None)

    def list_by_estado(self, estado: EstadoTrabajo):
        return [t for t in self._trabajos if t.estado == estado]

    def list_by_document(self, documento_id: str):
        return [t for t in self._trabajos if t.documento_id == documento_id]

    def list_pendientes_por_prioridad(self):
        return [t for t in self._trabajos if t.estado == EstadoTrabajo.PENDIENTE]

    def list(self):
        return list(self._trabajos)


class _FakeReportWriter(ReportWriter):
    def __init__(self) -> None:
        self.filas = None

    def escribir_inventario(self, filas):
        raise NotImplementedError

    def escribir_procesamiento(self, filas):
        self.filas = filas
        return "/tmp/informe_procesamiento.csv"

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
    }
    datos.update(overrides)
    return Documento(**datos)


def test_documento_sin_clasificar_y_sin_trabajo() -> None:
    writer = _FakeReportWriter()
    caso_de_uso = GenerarInformeProcesamiento(_FakeDocumentRepository([_documento("doc-1")]), _FakeTrabajoRepository(), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.tipo_procesamiento == "sin_clasificar"
    assert fila.herramienta == "N/D"
    assert fila.intentos_trabajo == 0
    assert fila.estado_trabajo == "sin_trabajo_asociado"


def test_documento_clasificado_ocr_mapea_herramienta() -> None:
    writer = _FakeReportWriter()
    documento = _documento("doc-1").avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.OCR)
    caso_de_uso = GenerarInformeProcesamiento(_FakeDocumentRepository([documento]), _FakeTrabajoRepository(), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.tipo_procesamiento == "ocr"
    assert "Tesseract" in fila.herramienta


def test_suma_intentos_de_trabajos_de_extraccion_del_documento() -> None:
    writer = _FakeReportWriter()
    documento = _documento("doc-1").avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    trabajo_1 = (
        Trabajo(proyecto_id="PROY-0001", tipo=TipoTrabajo.EXTRACCION, documento_id="doc-1")
        .iniciar_preparacion()
        .fallar("boom")
    )
    trabajo_2 = Trabajo(proyecto_id="PROY-0001", tipo=TipoTrabajo.EXTRACCION, documento_id="doc-1")
    otro_documento_trabajo = Trabajo(proyecto_id="PROY-0001", tipo=TipoTrabajo.EXTRACCION, documento_id="doc-2")
    trabajo_repo = _FakeTrabajoRepository([trabajo_1, trabajo_2, otro_documento_trabajo])
    caso_de_uso = GenerarInformeProcesamiento(_FakeDocumentRepository([documento]), trabajo_repo, writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.intentos_trabajo == 1  # solo trabajo_1 fallo una vez
    assert fila.estado_trabajo in ("fallido", "pendiente")


def test_ignora_trabajos_de_otro_tipo() -> None:
    writer = _FakeReportWriter()
    documento = _documento("doc-1").avanzar_a(EstadoDocumento.INVENTARIADO).clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
    trabajo_normalizacion = Trabajo(proyecto_id="PROY-0001", tipo=TipoTrabajo.NORMALIZACION, documento_id="doc-1")
    caso_de_uso = GenerarInformeProcesamiento(
        _FakeDocumentRepository([documento]), _FakeTrabajoRepository([trabajo_normalizacion]), writer
    )

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.estado_trabajo == "sin_trabajo_asociado"
