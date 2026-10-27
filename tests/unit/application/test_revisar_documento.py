"""RevisarDocumento (Modulo 8, primera pieza de backend real para la
GUI) y su cableado en DocumentsService. EXTRAIDO -> EN_REVISION ->
REVISADO en un solo paso atomico, mas la persistencia del historial
propio de `Revision` (ver domain.documents.entities.Revision /
domain.documents.ports.RevisionRepository) y el bloqueo real por
incidencias criticas abiertas (Modulo 13, ver
application.governance.service.GovernanceService)."""
from __future__ import annotations

from datetime import date

import pytest

from application.documents.commands.revisar_documento import RevisarDocumento
from application.governance.service import GovernanceService
from domain.documents.entities import Criticidad, Documento, EstadoDocumento, FormatoDocumento, Revision, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError, InvalidDocumentStateTransitionError
from domain.documents.ports import AprobacionRepository, DocumentRepository, RevisionRepository
from domain.governance.exceptions import IncidenciasCriticasAbiertasError, VigenciaDesconocidaError
from domain.incidents.entities import EtapaIncidencia, EstadoIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import Vigencia
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "e" * 64


class _FakeRevisionRepository(RevisionRepository):
    def __init__(self) -> None:
        self.guardadas: list[Revision] = []

    def save(self, revision: Revision) -> None:
        self.guardadas.append(revision)

    def list_by_document(self, documento_id: str) -> list[Revision]:
        return [r for r in self.guardadas if r.documento_id == documento_id]


class _FakeIncidentRepository(IncidentRepository):
    """Repositorio falso de incidencias -- usado aqui solo para
    construir un `GovernanceService` de prueba, no para probar
    persistencia (eso ya lo cubre test_sqlalchemy_incident_repository.py)."""

    def __init__(self, incidencias: list[Incidencia] | None = None) -> None:
        self._incidencias = list(incidencias or [])

    def save(self, incidencia: Incidencia) -> None:
        self._incidencias.append(incidencia)

    def get(self, incidencia_id: str):
        return next((i for i in self._incidencias if i.id == incidencia_id), None)

    def list_by_document(self, documento_id: str) -> list[Incidencia]:
        return [i for i in self._incidencias if i.documento_id == documento_id]

    def list(self) -> list[Incidencia]:
        return list(self._incidencias)


class _FakeVigenciaRepository(VigenciaRepository):
    """Repositorio falso de vigencias -- usado aqui solo para construir
    un `GovernanceService` de prueba (segunda regla de Modulo 13), no
    para probar persistencia (eso ya lo cubre
    test_sqlalchemy_validity_repository.py)."""

    def __init__(self, vigencias: list[Vigencia] | None = None) -> None:
        self._por_documento: dict[str, Vigencia] = {v.documento_id: v for v in (vigencias or [])}

    def save(self, vigencia: Vigencia) -> None:
        self._por_documento[vigencia.documento_id] = vigencia

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeFuenteRepository(FuenteRepository):
    """Sin fuentes por defecto -- esta prueba no ejercita la tercera
    regla de Modulo 13 (liberacion), solo la primera/segunda (ver
    test_governance_service.py para la tercera)."""

    def save(self, fuente) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


class _FakeAprobacionRepository(AprobacionRepository):
    def __init__(self) -> None:
        self._aprobaciones: list = []

    def save(self, aprobacion) -> None:
        self._aprobaciones.append(aprobacion)

    def list_by_document(self, documento_id: str):
        return [a for a in self._aprobaciones if a.documento_id == documento_id]


def _governance(
    incidencias: list[Incidencia] | None = None,
    document_repository: DocumentRepository | None = None,
    vigencias: list[Vigencia] | None = None,
) -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(incidencias),
        _FakeVigenciaRepository(vigencias),
        document_repository or _FakeDocumentRepository(),
        _FakeFuenteRepository(),
        _FakeAprobacionRepository(),
    )


def _incidencia_critica_abierta(documento_id: str) -> Incidencia:
    return Incidencia(
        proyecto_id="PROY-0001",
        documento_id=documento_id,
        etapa=EtapaIncidencia.REVISION,
        tipo="cifra_dudosa",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="La cifra de la pagina 3 no coincide con el original.",
        impacto="Podria invalidar el monto reportado.",
    )


def _documento_extraido(repo: _FakeDocumentRepository) -> Documento:
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
    )
    repo.save(documento)
    return documento


def test_revisar_documento_inexistente_falla() -> None:
    repo = _FakeDocumentRepository()
    caso_de_uso = RevisarDocumento(repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe", "ana@nexom.mx")


def test_revisar_documento_requiere_estado_extraido() -> None:
    repo = _FakeDocumentRepository()
    documento = Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
    )
    repo.save(documento)  # todavia en RECIBIDO

    caso_de_uso = RevisarDocumento(repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance())
    with pytest.raises(InvalidDocumentStateTransitionError):
        caso_de_uso.execute(documento.id, "ana@nexom.mx")


def test_revisar_documento_exitoso_avanza_a_revisado_y_audita() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    audit = _FakeAuditLogger()
    caso_de_uso = RevisarDocumento(repo, _FakeRevisionRepository(), audit, _governance())

    revisado = caso_de_uso.execute(documento.id, "ana@nexom.mx", "Se coteja contra el original, todo correcto.")

    assert revisado.estado == EstadoDocumento.REVISADO
    assert repo.get(documento.id).estado == EstadoDocumento.REVISADO
    assert [e.accion for e in audit.eventos] == ["revisar_documento"]
    assert audit.eventos[0].valor_nuevo == "ana@nexom.mx"
    assert audit.eventos[0].motivo == "Se coteja contra el original, todo correcto."


def test_revisar_documento_sin_comentario_usa_motivo_por_defecto() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    audit = _FakeAuditLogger()
    caso_de_uso = RevisarDocumento(repo, _FakeRevisionRepository(), audit, _governance())

    caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert "Revision contra el original completada" in audit.eventos[0].motivo


def test_revisor_vacio_es_rechazado() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    caso_de_uso = RevisarDocumento(repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance())

    with pytest.raises(ValueError):
        caso_de_uso.execute(documento.id, "   ")


def test_revisar_documento_guarda_un_registro_de_revision() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    revision_repo = _FakeRevisionRepository()
    caso_de_uso = RevisarDocumento(repo, revision_repo, _FakeAuditLogger(), _governance())

    caso_de_uso.execute(documento.id, "ana@nexom.mx", "Todo correcto.", ["inc-1", "inc-2"])

    revisiones = revision_repo.list_by_document(documento.id)
    assert len(revisiones) == 1
    assert revisiones[0].revisor == "ana@nexom.mx"
    assert revisiones[0].comentario == "Todo correcto."
    assert revisiones[0].incidencias_detectadas == ["inc-1", "inc-2"]


def test_revisar_documento_sin_incidencias_guarda_lista_vacia() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    revision_repo = _FakeRevisionRepository()
    caso_de_uso = RevisarDocumento(repo, revision_repo, _FakeAuditLogger(), _governance())

    caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert revision_repo.list_by_document(documento.id)[0].incidencias_detectadas == []


def test_revisar_documento_dos_veces_acumula_dos_revisiones() -> None:
    # Cada Revision es un registro nuevo e inmutable -- si un documento
    # vuelve a EXTRAIDO tras una correccion y se revisa otra vez, la
    # revision anterior no se sobrescribe (ver docstring de Revision).
    # Aqui se fuerza el estado de vuelta a EXTRAIDO directamente sobre
    # el repositorio (bypass de avanzar_a(), que hoy no expone ese
    # camino -- ver el docstring de ui.main_window sobre el alcance
    # deliberado del prototipo) solo para poder ejercitar la segunda
    # revision en esta prueba.
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    revision_repo = _FakeRevisionRepository()
    caso_de_uso = RevisarDocumento(repo, revision_repo, _FakeAuditLogger(), _governance())
    caso_de_uso.execute(documento.id, "ana@nexom.mx", "Primera revision.")

    revisado = repo.get(documento.id)
    de_vuelta = revisado.model_copy(update={"estado": EstadoDocumento.EXTRAIDO})
    repo.save(de_vuelta)
    caso_de_uso.execute(documento.id, "beto@nexom.mx", "Segunda revision.")

    revisiones = revision_repo.list_by_document(documento.id)
    assert len(revisiones) == 2
    assert {r.revisor for r in revisiones} == {"ana@nexom.mx", "beto@nexom.mx"}


# -- Modulo 13: bloqueo por incidencias criticas abiertas ------------


def test_revisar_documento_con_incidencia_critica_abierta_falla() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    incidencia = _incidencia_critica_abierta(documento.id)
    caso_de_uso = RevisarDocumento(
        repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance([incidencia])
    )

    with pytest.raises(IncidenciasCriticasAbiertasError):
        caso_de_uso.execute(documento.id, "ana@nexom.mx")

    # Ni el estado del documento ni la revision deben mutar si el
    # bloqueo se dispara -- la verificacion ocurre ANTES de avanzar_a().
    assert repo.get(documento.id).estado == EstadoDocumento.EXTRAIDO


def test_revisar_documento_con_incidencia_critica_ya_cerrada_no_bloquea() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    incidencia = _incidencia_critica_abierta(documento.id).model_copy(update={"estado": EstadoIncidencia.CERRADA})
    caso_de_uso = RevisarDocumento(
        repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance([incidencia])
    )

    revisado = caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert revisado.estado == EstadoDocumento.REVISADO


def test_revisar_documento_con_incidencia_no_critica_abierta_no_bloquea() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)
    incidencia = _incidencia_critica_abierta(documento.id).model_copy(update={"severidad": SeveridadIncidencia.ALTA})
    caso_de_uso = RevisarDocumento(
        repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance([incidencia])
    )

    revisado = caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert revisado.estado == EstadoDocumento.REVISADO


# -- Modulo 13: bloqueo por vigencia desconocida en documentos criticos --


def test_revisar_documento_critico_con_vigencia_desconocida_falla() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo).model_copy(update={"criticidad": Criticidad.CRITICO})
    repo.save(documento)
    caso_de_uso = RevisarDocumento(
        repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance(document_repository=repo)
    )

    with pytest.raises(VigenciaDesconocidaError):
        caso_de_uso.execute(documento.id, "ana@nexom.mx")

    # Ni el estado del documento ni la revision deben mutar si el
    # bloqueo se dispara -- la verificacion ocurre ANTES de avanzar_a().
    assert repo.get(documento.id).estado == EstadoDocumento.EXTRAIDO


def test_revisar_documento_critico_con_vigencia_completa_no_bloquea() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo).model_copy(update={"criticidad": Criticidad.CRITICO})
    repo.save(documento)
    vigencia = Vigencia(
        documento_id=documento.id,
        vigente_desde=date(2026, 1, 1),
        sin_vencimiento=True,
        autoridad="Direccion Juridica",
    )
    caso_de_uso = RevisarDocumento(
        repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance(document_repository=repo, vigencias=[vigencia])
    )

    revisado = caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert revisado.estado == EstadoDocumento.REVISADO


def test_revisar_documento_no_critico_con_vigencia_desconocida_no_bloquea() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_extraido(repo)  # criticidad por defecto: NO_CRITICO
    caso_de_uso = RevisarDocumento(
        repo, _FakeRevisionRepository(), _FakeAuditLogger(), _governance(document_repository=repo)
    )

    revisado = caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert revisado.estado == EstadoDocumento.REVISADO
