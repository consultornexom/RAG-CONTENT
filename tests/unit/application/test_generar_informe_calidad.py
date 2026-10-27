"""GenerarInformeCalidad (Fase 8, Documento Maestro seccion 7.1) --
reutiliza GovernanceService.verificar_documento_liberable() sin
duplicar la regla, mismo criterio que CerrarLote (Fase 7)."""
from __future__ import annotations

from application.governance.service import GovernanceService
from application.reports.commands.generar_informe_calidad import GenerarInformeCalidad
from domain.documents.entities import (
    Aprobacion,
    Documento,
    EstadoDocumento,
    FormatoDocumento,
    TipoProcesamiento,
)
from domain.documents.ports import AprobacionRepository
from domain.incidents.ports import IncidentRepository
from domain.reports.ports import ReportWriter
from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeDocumentRepository

_HASH = "2" * 64


class _FakeIncidentRepository(IncidentRepository):
    def save(self, incidencia) -> None:
        pass

    def get(self, incidencia_id: str):
        return None

    def list_by_document(self, documento_id: str):
        return []

    def list(self):
        return []


class _FakeVigenciaRepository(VigenciaRepository):
    def save(self, vigencia) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


class _FakeFuenteRepository(FuenteRepository):
    def __init__(self, fuentes: list[Fuente] | None = None) -> None:
        self._por_documento: dict[str, Fuente] = {f.documento_id: f for f in (fuentes or [])}

    def save(self, fuente: Fuente) -> None:
        self._por_documento[fuente.documento_id] = fuente

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


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
        self.filas = filas
        return "/tmp/informe_calidad.csv"

    def escribir_trazabilidad(self, filas):
        raise NotImplementedError

    def escribir_acta_cierre_lote(self, acta):
        raise NotImplementedError


def _governance(fuentes=None, aprobaciones=None, document_repository=None) -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        document_repository or _FakeDocumentRepository(),
        _FakeFuenteRepository(fuentes),
        _FakeAprobacionRepository(aprobaciones),
    )


def _documento_validado(documento_id: str) -> Documento:
    documento = Documento(
        id=documento_id,
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH,
        tamano_bytes=1024,
    )
    return (
        documento.avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md")
        .aprobar_para_markdown()
        .generar_markdown(f"/proyecto/07_markdown/{documento_id}.md", "hash-markdown")
        .validar_markdown()
    )


def test_documento_recibido_incumple_por_falta_de_fuente_y_aprobacion() -> None:
    writer = _FakeReportWriter()
    documento = Documento(
        id="doc-1",
        proyecto_id="PROY-0001",
        nombre_original="memo.txt",
        formato=FormatoDocumento.TXT,
        ruta_origen="/tmp/x/memo.txt",
        ruta_copia_original="/proyecto/01_originales/abc_memo.txt",
        hash_sha256=_HASH,
        tamano_bytes=10,
    )
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = GenerarInformeCalidad(document_repo, _governance(document_repository=document_repo), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.incumplimientos != []
    assert fila.semaforo == "amarillo"


def test_documento_liberado_sin_incumplimientos_semaforo_verde() -> None:
    writer = _FakeReportWriter()
    documento = _documento_validado("doc-1").liberar()
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = GenerarInformeCalidad(document_repo, _governance(document_repository=document_repo), writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.incumplimientos == []
    assert fila.semaforo == "verde"


def test_documento_bloqueado_semaforo_rojo() -> None:
    writer = _FakeReportWriter()
    documento = _documento_validado("doc-1").avanzar_a(EstadoDocumento.BLOQUEADO)
    document_repo = _FakeDocumentRepository([documento])
    caso_de_uso = GenerarInformeCalidad(document_repo, _governance(document_repository=document_repo), writer)

    caso_de_uso.execute()

    assert writer.filas[0].semaforo == "rojo"


def test_documento_validado_con_fuente_y_aprobacion_sin_incumplimientos() -> None:
    writer = _FakeReportWriter()
    documento = _documento_validado("doc-1")
    document_repo = _FakeDocumentRepository([documento])
    fuente = Fuente(documento_id="doc-1", sistema_origen="portal", autoridad="RH", evidencia_consulta="confirmado")
    aprobacion = Aprobacion(documento_id="doc-1", aprobador="ana@nexom.mx")
    governance = _governance(fuentes=[fuente], aprobaciones=[aprobacion], document_repository=document_repo)
    caso_de_uso = GenerarInformeCalidad(document_repo, governance, writer)

    caso_de_uso.execute()

    fila = writer.filas[0]
    assert fila.incumplimientos == []
    assert fila.semaforo == "verde"
