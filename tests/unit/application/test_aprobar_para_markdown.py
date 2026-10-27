"""AprobarParaMarkdown (Modulo 12/13, Documento Maestro seccion 4.6.1 y
4.7): NORMALIZADO -> PENDIENTE_DE_APROBACION -> APROBADO_PARA_MARKDOWN
en un solo paso atomico, mas el registro de `Aprobacion` (historial) y
la reutilizacion de la misma regla de gobernanza que ya aplica
RevisarDocumento (incidencias criticas / vigencia desconocida)."""
from __future__ import annotations

import pytest

from application.documents.commands.aprobar_para_markdown import AprobarParaMarkdown
from application.governance.service import GovernanceService
from domain.documents.entities import Criticidad, Documento, EstadoDocumento, FormatoDocumento, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import AprobacionRepository, DocumentRepository
from domain.governance.exceptions import IncidenciasCriticasAbiertasError, VigenciaDesconocidaError
from domain.incidents.entities import EstadoIncidencia, EtapaIncidencia, Incidencia, SeveridadIncidencia
from domain.incidents.ports import IncidentRepository
from domain.validity.entities import Vigencia
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "f" * 64


class _FakeAprobacionRepository(AprobacionRepository):
    def __init__(self) -> None:
        self.guardadas: list = []

    def save(self, aprobacion) -> None:
        self.guardadas.append(aprobacion)

    def list_by_document(self, documento_id: str):
        return [a for a in self.guardadas if a.documento_id == documento_id]


class _FakeIncidentRepository(IncidentRepository):
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
    def __init__(self, vigencias: list[Vigencia] | None = None) -> None:
        self._por_documento: dict[str, Vigencia] = {v.documento_id: v for v in (vigencias or [])}

    def save(self, vigencia: Vigencia) -> None:
        self._por_documento[vigencia.documento_id] = vigencia

    def get_by_document(self, documento_id: str):
        return self._por_documento.get(documento_id)


class _FakeFuenteRepository(FuenteRepository):
    def save(self, fuente) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


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


def _documento_normalizado(repo: _FakeDocumentRepository, criticidad: Criticidad = Criticidad.NO_CRITICO) -> Documento:
    documento = Documento(
        proyecto_id="PROY-0001",
        nombre_original="politica.pdf",
        formato=FormatoDocumento.PDF,
        ruta_origen="/tmp/x/politica.pdf",
        ruta_copia_original="/proyecto/01_originales/abc_politica.pdf",
        hash_sha256=_HASH_VALIDO,
        tamano_bytes=1024,
        criticidad=criticidad,
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
    )
    repo.save(documento)
    return documento


def test_aprobar_documento_inexistente_falla() -> None:
    repo = _FakeDocumentRepository()
    caso_de_uso = AprobarParaMarkdown(repo, _FakeAprobacionRepository(), _FakeAuditLogger(), _governance())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe", "ana@nexom.mx")


def test_aprobador_vacio_es_rechazado() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_normalizado(repo)
    caso_de_uso = AprobarParaMarkdown(repo, _FakeAprobacionRepository(), _FakeAuditLogger(), _governance())
    with pytest.raises(ValueError):
        caso_de_uso.execute(documento.id, "   ")


def test_aprobar_exitoso_avanza_a_aprobado_para_markdown_y_audita() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_normalizado(repo)
    audit = _FakeAuditLogger()
    caso_de_uso = AprobarParaMarkdown(repo, _FakeAprobacionRepository(), audit, _governance())

    aprobado = caso_de_uso.execute(documento.id, "ana@nexom.mx", "Todo en orden.")

    assert aprobado.estado == EstadoDocumento.APROBADO_PARA_MARKDOWN
    assert repo.get(documento.id).estado == EstadoDocumento.APROBADO_PARA_MARKDOWN
    assert [e.accion for e in audit.eventos] == ["aprobar_para_markdown"]
    assert audit.eventos[0].valor_nuevo == "ana@nexom.mx"


def test_aprobar_guarda_un_registro_de_aprobacion() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_normalizado(repo)
    aprobacion_repo = _FakeAprobacionRepository()
    caso_de_uso = AprobarParaMarkdown(repo, aprobacion_repo, _FakeAuditLogger(), _governance())

    caso_de_uso.execute(documento.id, "ana@nexom.mx", "Todo en orden.")

    aprobaciones = aprobacion_repo.list_by_document(documento.id)
    assert len(aprobaciones) == 1
    assert aprobaciones[0].aprobador == "ana@nexom.mx"
    assert aprobaciones[0].comentario == "Todo en orden."


def test_aprobar_con_incidencia_critica_abierta_falla() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_normalizado(repo)
    incidencia = Incidencia(
        proyecto_id="PROY-0001",
        documento_id=documento.id,
        etapa=EtapaIncidencia.REVISION,
        tipo="cifra_dudosa",
        severidad=SeveridadIncidencia.CRITICA,
        evidencia="La cifra de la pagina 3 no coincide.",
        impacto="Podria invalidar el monto reportado.",
        estado=EstadoIncidencia.ABIERTA,
    )
    caso_de_uso = AprobarParaMarkdown(repo, _FakeAprobacionRepository(), _FakeAuditLogger(), _governance([incidencia]))

    with pytest.raises(IncidenciasCriticasAbiertasError):
        caso_de_uso.execute(documento.id, "ana@nexom.mx")

    # Ni el estado del documento ni la aprobacion deben mutar si el
    # bloqueo se dispara.
    assert repo.get(documento.id).estado == EstadoDocumento.NORMALIZADO


def test_aprobar_documento_critico_con_vigencia_desconocida_falla() -> None:
    repo = _FakeDocumentRepository()
    documento = _documento_normalizado(repo, criticidad=Criticidad.CRITICO)
    caso_de_uso = AprobarParaMarkdown(
        repo, _FakeAprobacionRepository(), _FakeAuditLogger(), _governance(document_repository=repo)
    )

    with pytest.raises(VigenciaDesconocidaError):
        caso_de_uso.execute(documento.id, "ana@nexom.mx")

    assert repo.get(documento.id).estado == EstadoDocumento.NORMALIZADO
