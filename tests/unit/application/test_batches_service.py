"""BatchesService (Fase 7): pruebas de la fachada en si -- las reglas
de cada caso de uso ya estan cubiertas por test_crear_lote.py,
test_agregar_quitar_documento_lote.py y test_cerrar_lote.py; aqui solo
se verifica que la fachada delega y compone correctamente (mismo
criterio de cobertura que el resto de fachadas de este proyecto)."""
from __future__ import annotations

from application.batches.service import BatchesService
from application.governance.service import GovernanceService
from domain.batches.entities import Lote
from domain.batches.ports import LoteRepository
from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento
from domain.incidents.ports import IncidentRepository
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "1" * 64


class _FakeLoteRepository(LoteRepository):
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
    def save(self, fuente) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


class _FakeAprobacionRepository:
    def save(self, aprobacion) -> None:
        pass

    def list_by_document(self, documento_id: str):
        return []


def _documento(documento_id: str, **overrides) -> Documento:
    datos = {
        "id": documento_id,
        "proyecto_id": "PROY-0001",
        "nombre_original": "politica.pdf",
        "formato": FormatoDocumento.PDF,
        "ruta_origen": "/tmp/x/politica.pdf",
        "ruta_copia_original": "/proyecto/01_originales/abc_politica.pdf",
        "hash_sha256": _HASH_VALIDO,
        "tamano_bytes": 1024,
    }
    datos.update(overrides)
    return Documento(**datos)


def _servicio(lotes=None, documentos=None) -> BatchesService:
    document_repository = _FakeDocumentRepository(documentos)
    governance = GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        document_repository,
        _FakeFuenteRepository(),
        _FakeAprobacionRepository(),
    )
    return BatchesService(_FakeLoteRepository(lotes), document_repository, governance, _FakeAuditLogger())


def test_crear_agregar_y_obtener_lote() -> None:
    servicio = _servicio(documentos=[_documento("doc-1")])
    lote = servicio.crear_lote("PROY-0001", "Lote 1")
    servicio.agregar_documento(lote.id, "doc-1")

    assert servicio.obtener_lote(lote.id) == lote
    assert servicio.listar_documentos_del_lote(lote.id)[0].id == "doc-1"


def test_listar_lotes_filtra_por_proyecto() -> None:
    servicio = _servicio()
    servicio.crear_lote("PROY-0001", "Lote A")
    servicio.crear_lote("PROY-0002", "Lote B")

    lotes_proy_1 = servicio.listar_lotes("PROY-0001")
    assert len(lotes_proy_1) == 1
    assert lotes_proy_1[0].nombre == "Lote A"


def test_quitar_documento_via_fachada() -> None:
    servicio = _servicio(documentos=[_documento("doc-1")])
    lote = servicio.crear_lote("PROY-0001", "Lote 1")
    servicio.agregar_documento(lote.id, "doc-1")

    resultado = servicio.quitar_documento("doc-1")

    assert resultado.lote_id is None
    assert servicio.listar_documentos_del_lote(lote.id) == []


def test_obtener_lote_inexistente_devuelve_none() -> None:
    servicio = _servicio()
    assert servicio.obtener_lote("no-existe") is None


def test_cerrar_lote_via_fachada() -> None:
    """El escenario completo (liberar/bloquear) ya lo cubre
    test_cerrar_lote.py -- aqui solo se verifica que la fachada delega
    en CerrarLote de verdad."""
    documento = _documento("doc-1").avanzar_a(EstadoDocumento.INVENTARIADO)  # sin llegar a VALIDADO
    servicio = _servicio(documentos=[documento])
    lote = servicio.crear_lote("PROY-0001", "Lote 1")
    servicio.agregar_documento(lote.id, "doc-1")

    cerrado = servicio.cerrar_lote(lote.id)

    assert cerrado.estado.value == "cerrado"
    assert servicio.listar_documentos_del_lote(lote.id)[0].estado == EstadoDocumento.BLOQUEADO
