"""ReportsService (Fase 8): pruebas de la fachada en si -- las reglas de
cada caso de uso ya estan cubiertas por sus propios archivos de prueba;
aqui solo se verifica que la fachada delega y compone correctamente
(mismo criterio de cobertura que el resto de fachadas de este
proyecto -- ver test_batches_service.py)."""
from __future__ import annotations

from application.governance.service import GovernanceService
from application.reports.service import ReportsService
from domain.batches.entities import Lote
from domain.documents.entities import Documento, FormatoDocumento
from domain.incidents.ports import IncidentRepository
from domain.jobs.entities import EstadoTrabajo
from domain.reports.ports import ReportWriter
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "5" * 64


class _FakeVigenciaRepository(VigenciaRepository):
    def save(self, vigencia) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


class _FakeFuenteRepository(FuenteRepository):
    def save(self, fuente) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


class _FakeAprobacionRepository:
    def save(self, aprobacion) -> None:
        pass

    def list_by_document(self, documento_id: str):
        return []


class _FakeRevisionRepository:
    def save(self, revision) -> None:
        pass

    def list_by_document(self, documento_id: str):
        return []


class _FakeIncidentRepository(IncidentRepository):
    def save(self, incidencia) -> None:
        pass

    def get(self, incidencia_id: str):
        return None

    def list_by_document(self, documento_id: str):
        return []

    def list(self):
        return []


class _FakeTrabajoRepository:
    def save(self, trabajo) -> None:
        pass

    def get(self, trabajo_id: str):
        return None

    def list_by_estado(self, estado: EstadoTrabajo):
        return []

    def list_by_document(self, documento_id: str):
        return []

    def list_pendientes_por_prioridad(self):
        return []

    def list(self):
        return []


class _FakeLoteRepository:
    def __init__(self, lotes: list[Lote] | None = None) -> None:
        self._por_id: dict[str, Lote] = {lote.id: lote for lote in (lotes or [])}

    def save(self, lote: Lote) -> None:
        self._por_id[lote.id] = lote

    def get(self, lote_id: str):
        return self._por_id.get(lote_id)

    def list_by_proyecto(self, proyecto_id: str):
        return [lote for lote in self._por_id.values() if lote.proyecto_id == proyecto_id]

    def list(self):
        return list(self._por_id.values())


class _FakeReportWriter(ReportWriter):
    def escribir_inventario(self, filas):
        return "/tmp/informe_inventario.csv"

    def escribir_procesamiento(self, filas):
        return "/tmp/informe_procesamiento.csv"

    def escribir_revision(self, filas):
        return "/tmp/informe_revision.csv"

    def escribir_incidencias(self, filas):
        return "/tmp/informe_incidencias.csv"

    def escribir_calidad(self, filas):
        return "/tmp/informe_calidad.csv"

    def escribir_trazabilidad(self, filas):
        return "/tmp/informe_trazabilidad.csv"

    def escribir_acta_cierre_lote(self, acta):
        return f"/tmp/acta_cierre_lote_{acta.lote_id}.md"


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


def _servicio(documentos=None, lotes=None) -> ReportsService:
    document_repository = _FakeDocumentRepository(documentos)
    governance = GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        document_repository,
        _FakeFuenteRepository(),
        _FakeAprobacionRepository(),
    )
    return ReportsService(
        document_repository,
        _FakeVigenciaRepository(),
        _FakeTrabajoRepository(),
        _FakeRevisionRepository(),
        _FakeIncidentRepository(),
        _FakeAprobacionRepository(),
        _FakeLoteRepository(lotes),
        governance,
        _FakeReportWriter(),
    )


def test_cada_informe_delega_en_su_caso_de_uso() -> None:
    servicio = _servicio(documentos=[_documento("doc-1")])

    assert servicio.generar_informe_inventario() == "/tmp/informe_inventario.csv"
    assert servicio.generar_informe_procesamiento() == "/tmp/informe_procesamiento.csv"
    assert servicio.generar_informe_revision() == "/tmp/informe_revision.csv"
    assert servicio.generar_informe_incidencias() == "/tmp/informe_incidencias.csv"
    assert servicio.generar_informe_calidad() == "/tmp/informe_calidad.csv"
    assert servicio.generar_informe_trazabilidad() == "/tmp/informe_trazabilidad.csv"


def test_generar_acta_cierre_lote_via_fachada() -> None:
    lote = Lote(proyecto_id="PROY-0001", nombre="Lote 1").cerrar()
    servicio = _servicio(lotes=[lote])

    assert servicio.generar_acta_cierre_lote(lote.id) == f"/tmp/acta_cierre_lote_{lote.id}.md"


def test_generar_todos_los_informes_devuelve_las_seis_rutas() -> None:
    servicio = _servicio(documentos=[_documento("doc-1")])

    rutas = servicio.generar_todos_los_informes()

    assert set(rutas) == {"inventario", "procesamiento", "revision", "incidencias", "calidad", "trazabilidad"}
    assert rutas["inventario"] == "/tmp/informe_inventario.csv"
