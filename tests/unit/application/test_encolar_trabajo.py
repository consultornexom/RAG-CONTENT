"""EncolarTrabajo (Fase 6): valida que el documento referenciado exista
antes de encolar el trabajo -- mismo patron que RegistrarIncidencia."""
from __future__ import annotations

import pytest

from application.jobs.commands.encolar_trabajo import EncolarTrabajo
from domain.documents.entities import Documento, FormatoDocumento
from domain.documents.exceptions import DocumentNotFoundError
from domain.jobs.entities import EstadoTrabajo, Prioridad, Trabajo, TipoTrabajo
from domain.jobs.ports import TrabajoRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "7" * 64


class _FakeTrabajoRepository(TrabajoRepository):
    def __init__(self) -> None:
        self._por_id: dict[str, Trabajo] = {}

    def save(self, trabajo: Trabajo) -> None:
        self._por_id[trabajo.id] = trabajo

    def get(self, trabajo_id: str):
        return self._por_id.get(trabajo_id)

    def list(self):
        return list(self._por_id.values())

    def list_by_estado(self, estado: EstadoTrabajo):
        return [t for t in self._por_id.values() if t.estado == estado]

    def list_by_document(self, documento_id: str):
        return [t for t in self._por_id.values() if t.documento_id == documento_id]

    def list_pendientes_por_prioridad(self):
        return self.list_by_estado(EstadoTrabajo.PENDIENTE)


def _documento() -> Documento:
    return Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )


def test_encolar_sobre_documento_inexistente_falla() -> None:
    caso_de_uso = EncolarTrabajo(_FakeTrabajoRepository(), _FakeDocumentRepository(), _FakeAuditLogger())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("PROY-0001", TipoTrabajo.EXTRACCION, "no-existe")


def test_encolar_exitoso_crea_trabajo_pendiente() -> None:
    documento = _documento()
    document_repo = _FakeDocumentRepository([documento])
    trabajo_repo = _FakeTrabajoRepository()
    audit = _FakeAuditLogger()
    caso_de_uso = EncolarTrabajo(trabajo_repo, document_repo, audit)

    trabajo = caso_de_uso.execute("PROY-0001", TipoTrabajo.EXTRACCION, documento.id, Prioridad.ALTA)

    assert trabajo.estado == EstadoTrabajo.PENDIENTE
    assert trabajo.tipo == TipoTrabajo.EXTRACCION
    assert trabajo.documento_id == documento.id
    assert trabajo.prioridad == Prioridad.ALTA
    assert trabajo_repo.get(trabajo.id) == trabajo
    assert [e.accion for e in audit.eventos] == ["encolar_trabajo"]


def test_encolar_usa_prioridad_normal_y_tres_intentos_por_defecto() -> None:
    documento = _documento()
    caso_de_uso = EncolarTrabajo(_FakeTrabajoRepository(), _FakeDocumentRepository([documento]), _FakeAuditLogger())

    trabajo = caso_de_uso.execute("PROY-0001", TipoTrabajo.NORMALIZACION, documento.id)

    assert trabajo.prioridad == Prioridad.NORMAL
    assert trabajo.max_intentos == 3
