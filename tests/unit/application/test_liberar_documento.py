"""LiberarDocumento (Modulo 12/13, Documento Maestro seccion 4.7): "no
liberar contenido sin fuente, hash y aprobacion". VALIDADO -> LIBERADO,
bloqueado por GovernanceService.verificar_documento_liberable()."""
from __future__ import annotations

import pytest

from application.documents.commands.liberar_documento import LiberarDocumento
from application.governance.service import GovernanceService
from domain.documents.entities import Aprobacion, Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import AprobacionRepository
from domain.governance.exceptions import AprobacionFaltanteError, FuenteFaltanteError
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import Fuente
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "3" * 64


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

    def list_by_document(self, documento_id: str) -> list[Aprobacion]:
        return [a for a in self._aprobaciones if a.documento_id == documento_id]


def _governance(fuentes: list[Fuente] | None = None, aprobaciones: list[Aprobacion] | None = None) -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        _FakeDocumentRepository(),
        _FakeFuenteRepository(fuentes),
        _FakeAprobacionRepository(aprobaciones),
    )


def _documento_validado(repo: _FakeDocumentRepository) -> Documento:
    documento = Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )
    documento = (
        documento.avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion("/proyecto/03_extracciones/doc.md")
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
        .avanzar_a(EstadoDocumento.EN_NORMALIZACION)
        .completar_normalizacion("/proyecto/06_normalizados/doc.md")
        .aprobar_para_markdown()
        .generar_markdown("/proyecto/07_markdown/doc.md", "hash-de-prueba")
        .validar_markdown()
    )
    repo.save(documento)
    return documento


def test_liberar_documento_inexistente_falla() -> None:
    repo = _FakeDocumentRepository()
    caso_de_uso = LiberarDocumento(repo, _FakeAuditLogger(), _governance())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe")


def test_liberar_sin_fuente_falla() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_validado(repo)
    governance = _governance(aprobaciones=[Aprobacion(documento_id=documento.id, aprobador="ana@nexom.mx")])
    caso_de_uso = LiberarDocumento(repo, _FakeAuditLogger(), governance)

    with pytest.raises(FuenteFaltanteError):
        caso_de_uso.execute(documento.id)

    assert repo.get(documento.id).estado == EstadoDocumento.VALIDADO


def test_liberar_sin_aprobacion_falla() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_validado(repo)
    fuente = Fuente(
        documento_id=documento.id,
        sistema_origen="portal interno",
        autoridad="Direccion Juridica",
        evidencia_consulta="Confirmado el 2026-07-28.",
    )
    governance = _governance(fuentes=[fuente])
    caso_de_uso = LiberarDocumento(repo, _FakeAuditLogger(), governance)

    with pytest.raises(AprobacionFaltanteError):
        caso_de_uso.execute(documento.id)

    assert repo.get(documento.id).estado == EstadoDocumento.VALIDADO


def test_liberar_exitoso_con_fuente_y_aprobacion() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_validado(repo)
    fuente = Fuente(
        documento_id=documento.id,
        sistema_origen="portal interno",
        autoridad="Direccion Juridica",
        evidencia_consulta="Confirmado el 2026-07-28.",
    )
    governance = _governance(
        fuentes=[fuente], aprobaciones=[Aprobacion(documento_id=documento.id, aprobador="ana@nexom.mx")]
    )
    audit = _FakeAuditLogger()
    caso_de_uso = LiberarDocumento(repo, audit, governance)

    liberado = caso_de_uso.execute(documento.id)

    assert liberado.estado == EstadoDocumento.LIBERADO
    assert repo.get(documento.id).estado == EstadoDocumento.LIBERADO
    assert [e.accion for e in audit.eventos] == ["liberar_documento"]
