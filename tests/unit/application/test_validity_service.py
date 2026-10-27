"""ValidityService (Modulo 11, Documento Maestro seccion 4.6, fila 11:
"Vigencias y fuentes"). Prueba tanto la fachada como la validacion
cruzada hacia el contexto Documentos (mismo patron que
RegistrarIncidencia con DocumentRepository)."""
from __future__ import annotations

from datetime import date

import pytest

from application.validity.service import ValidityService
from domain.documents.entities import Documento, FormatoDocumento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.validity.entities import Fuente, Vigencia
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger

_HASH_VALIDO = "d" * 64


class _FakeDocumentRepository(DocumentRepository):
    def __init__(self, documentos: list[Documento] | None = None) -> None:
        self._por_id = {d.id: d for d in (documentos or [])}

    def save(self, documento: Documento) -> None:
        self._por_id[documento.id] = documento

    def get(self, documento_id: str):
        return self._por_id.get(documento_id)

    def get_by_hash(self, hash_sha256: str):
        return next((d for d in self._por_id.values() if d.hash_sha256 == hash_sha256), None)

    def list_by_estado(self, estado):
        return [d for d in self._por_id.values() if d.estado == estado]

    def list(self):
        return list(self._por_id.values())


class _FakeFuenteRepository(FuenteRepository):
    def __init__(self) -> None:
        self._por_documento: dict[str, Fuente] = {}

    def save(self, fuente: Fuente) -> None:
        self._por_documento[fuente.documento_id] = fuente

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeVigenciaRepository(VigenciaRepository):
    def __init__(self) -> None:
        self._por_documento: dict[str, Vigencia] = {}

    def save(self, vigencia: Vigencia) -> None:
        self._por_documento[vigencia.documento_id] = vigencia

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


def _documento(**overrides) -> Documento:
    datos = {
        "proyecto_id": "PROY-0001",
        "nombre_original": "politica_vacaciones.pdf",
        "formato": FormatoDocumento.PDF,
        "ruta_origen": "/tmp/origen/politica_vacaciones.pdf",
        "ruta_copia_original": "/proyecto/01_originales/abc_politica_vacaciones.pdf",
        "hash_sha256": _HASH_VALIDO,
        "tamano_bytes": 1024,
    }
    datos.update(overrides)
    return Documento(**datos)


@pytest.fixture()
def entorno():
    documento = _documento()
    document_repository = _FakeDocumentRepository([documento])
    fuente_repository = _FakeFuenteRepository()
    vigencia_repository = _FakeVigenciaRepository()
    audit = _FakeAuditLogger()
    servicio = ValidityService(fuente_repository, vigencia_repository, document_repository, audit)
    return servicio, documento, document_repository, audit


def test_registrar_fuente_documento_inexistente_falla(entorno) -> None:
    servicio, _documento, _repo, _audit = entorno
    with pytest.raises(DocumentNotFoundError):
        servicio.registrar_fuente("no-existe", "sistema", "autoridad", "evidencia")


def test_registrar_fuente_nueva_se_puede_consultar_despues(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    servicio.registrar_fuente(documento.id, "portal interno", "Direccion Juridica", "consultado el 2026-07-28")

    fuente = servicio.obtener_fuente(documento.id)
    assert fuente is not None
    assert fuente.sistema_origen == "portal interno"
    assert fuente.autoridad == "Direccion Juridica"


def test_registrar_fuente_existente_la_actualiza_en_vez_de_duplicar(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    servicio.registrar_fuente(documento.id, "sistema v1", "autoridad v1", "evidencia v1")
    servicio.registrar_fuente(documento.id, "sistema v2", "autoridad v2", "evidencia v2")

    fuente = servicio.obtener_fuente(documento.id)
    assert fuente is not None
    assert fuente.sistema_origen == "sistema v2"


def test_registrar_fuente_deja_evento_de_auditoria(entorno) -> None:
    servicio, documento, _repo, audit = entorno
    servicio.registrar_fuente(documento.id, "sistema", "autoridad", "evidencia")

    assert [e.accion for e in audit.eventos] == ["registrar_fuente"]


def test_obtener_fuente_sin_registrar_es_none(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    assert servicio.obtener_fuente(documento.id) is None


def test_registrar_vigencia_documento_inexistente_falla(entorno) -> None:
    servicio, _documento, _repo, _audit = entorno
    with pytest.raises(DocumentNotFoundError):
        servicio.registrar_vigencia("no-existe", None, None, None, False, "")


def test_registrar_vigencia_sustituye_a_inexistente_falla(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    with pytest.raises(DocumentNotFoundError):
        servicio.registrar_vigencia(
            documento.id, None, date(2026, 1, 1), date(2026, 12, 31), False, "Direccion Juridica", "no-existe"
        )


def test_registrar_vigencia_sustituye_a_valido_se_acepta(entorno) -> None:
    servicio, documento, repo, _audit = entorno
    otro = _documento(nombre_original="version_anterior.pdf")
    repo.save(otro)

    vigencia = servicio.registrar_vigencia(
        documento.id, None, date(2026, 1, 1), date(2026, 12, 31), False, "Direccion Juridica", otro.id
    )
    assert vigencia.sustituye_a == otro.id


def test_registrar_vigencia_completa_se_puede_consultar_despues(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    servicio.registrar_vigencia(
        documento.id, date(2025, 12, 1), date(2026, 1, 1), date(2026, 12, 31), False, "Direccion Juridica"
    )

    vigencia = servicio.obtener_vigencia(documento.id)
    assert vigencia is not None
    assert vigencia.esta_completa() is True


def test_registrar_vigencia_parcial_queda_incompleta(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    servicio.registrar_vigencia(documento.id, None, date(2026, 1, 1), None, False, "")

    vigencia = servicio.obtener_vigencia(documento.id)
    assert vigencia is not None
    assert vigencia.esta_completa() is False


def test_registrar_vigencia_existente_la_actualiza_en_vez_de_duplicar(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    servicio.registrar_vigencia(documento.id, None, date(2026, 1, 1), date(2026, 12, 31), False, "autoridad v1")
    servicio.registrar_vigencia(documento.id, None, date(2026, 2, 1), date(2027, 1, 1), False, "autoridad v2")

    vigencia = servicio.obtener_vigencia(documento.id)
    assert vigencia is not None
    assert vigencia.autoridad == "autoridad v2"
    assert vigencia.vigente_desde == date(2026, 2, 1)


def test_registrar_vigencia_deja_evento_de_auditoria_con_estado_de_completitud(entorno) -> None:
    servicio, documento, _repo, audit = entorno
    servicio.registrar_vigencia(
        documento.id, None, date(2026, 1, 1), date(2026, 12, 31), False, "Direccion Juridica"
    )

    assert audit.eventos[-1].accion == "registrar_vigencia"
    assert audit.eventos[-1].valor_nuevo == "completa"


def test_obtener_vigencia_sin_registrar_es_none(entorno) -> None:
    servicio, documento, _repo, _audit = entorno
    assert servicio.obtener_vigencia(documento.id) is None
