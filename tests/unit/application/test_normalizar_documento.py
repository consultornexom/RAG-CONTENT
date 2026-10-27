"""NormalizarDocumento (Modulo 9) y su cableado en DocumentsService.
Motor y reglas de normalizacion en si ya se prueban con profundidad en
test_rule_based_normalization_engine.py -- aqui se prueba el caso de
uso: el requisito de estado REVISADO, el registro de auditoria, y que
el resultado se guarde en el store correcto (06_normalizados/, no
03_extracciones/).
"""
from __future__ import annotations

import pytest

from application.documents.commands.normalizar_documento import NormalizarDocumento
from application.documents.service import DocumentsService
from application.governance.service import GovernanceService
from domain.documents.entities import Documento, EstadoDocumento, FormatoDocumento, ResultadoNormalizacion, TipoProcesamiento
from domain.documents.exceptions import DocumentNotFoundError, InvalidDocumentStateTransitionError
from domain.documents.ports import (
    AprobacionRepository,
    ExtractionOutputStore,
    NormalizationEngine,
    RevisionRepository,
)
from domain.incidents.ports import IncidentRepository
from domain.profiles.entities import ReglaNormalizacion
from domain.validity.ports import FuenteRepository, VigenciaRepository
from tests.unit.application._fakes import _FakeAuditLogger, _FakeDocumentRepository

_HASH_VALIDO = "c" * 64


class _FakeNormalizationEngine(NormalizationEngine):
    def __init__(self, cambios: list[str] | None = None, excepcion: Exception | None = None):
        self.cambios = cambios or ["cambio de prueba"]
        self.llamadas: list[tuple[str, list[ReglaNormalizacion]]] = []
        # Simula un motor de normalizacion que falla (ver
        # test_normalizar_documento_fallido_no_deja_el_documento_atascado).
        self.excepcion = excepcion

    def normalizar(self, markdown: str, reglas: list[ReglaNormalizacion]) -> ResultadoNormalizacion:
        self.llamadas.append((markdown, reglas))
        if self.excepcion is not None:
            raise self.excepcion
        return ResultadoNormalizacion(markdown_normalizado=f"{markdown} [normalizado]", cambios=self.cambios)


class _FakeOutputStore(ExtractionOutputStore):
    def __init__(self, carpeta: str) -> None:
        self.carpeta = carpeta
        self.guardados: dict[str, str] = {}

    def guardar(self, documento_id: str, markdown: str) -> str:
        ruta = f"/proyecto/{self.carpeta}/{documento_id}.md"
        self.guardados[ruta] = markdown
        return ruta


class _FakeRevisionRepository(RevisionRepository):
    def __init__(self) -> None:
        self.guardadas: list = []

    def save(self, revision) -> None:
        self.guardadas.append(revision)

    def list_by_document(self, documento_id: str):
        return [r for r in self.guardadas if r.documento_id == documento_id]


class _FakeIncidentRepository(IncidentRepository):
    """Sin incidencias por defecto -- suficiente para un
    GovernanceService (Modulo 13) que nunca bloquea en estas pruebas."""

    def save(self, incidencia) -> None:
        pass

    def get(self, incidencia_id: str):
        return None

    def list_by_document(self, documento_id: str):
        return []

    def list(self):
        return []


class _FakeVigenciaRepository(VigenciaRepository):
    """Sin vigencias por defecto -- estas pruebas no ejercitan la
    segunda regla de Modulo 13; el `DocumentRepository` que se le pasa
    a `GovernanceService` aqui esta siempre vacio, asi que la regla se
    salta sin importar el contenido de este repositorio."""

    def save(self, vigencia) -> None:
        pass

    def get_by_document(self, documento_id: str):
        return None


class _FakeFuenteRepository(FuenteRepository):
    """Sin fuentes por defecto -- estas pruebas no ejercitan la tercera
    regla de Modulo 13 (liberacion, ver test_liberar_documento.py)."""

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


def _governance_sin_bloqueos() -> GovernanceService:
    return GovernanceService(
        _FakeIncidentRepository(),
        _FakeVigenciaRepository(),
        _FakeDocumentRepository(),
        _FakeFuenteRepository(),
        _FakeAprobacionRepository(),
    )


def _documento_revisado(repo: _FakeDocumentRepository, ruta_extraccion: str = "/proyecto/03_extracciones/doc.md") -> Documento:
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
        .completar_extraccion(ruta_extraccion)
        .avanzar_a(EstadoDocumento.EN_REVISION)
        .avanzar_a(EstadoDocumento.REVISADO)
    )
    repo.save(documento)
    return documento


def test_normalizar_documento_inexistente_falla() -> None:
    repo = _FakeDocumentRepository()
    caso_de_uso = NormalizarDocumento(repo, _FakeNormalizationEngine(), [], _FakeOutputStore("06_normalizados"), _FakeAuditLogger())
    with pytest.raises(DocumentNotFoundError):
        caso_de_uso.execute("no-existe")


def test_normalizar_documento_requiere_estado_revisado(tmp_path) -> None:
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
    documento = (
        documento.avanzar_a(EstadoDocumento.INVENTARIADO)
        .clasificar(TipoProcesamiento.EXTRACCION_DIRECTA)
        .avanzar_a(EstadoDocumento.EN_EXTRACCION)
        .completar_extraccion(str(tmp_path / "doc.md"))
    )  # EXTRAIDO, todavia sin pasar por revision (Modulo 8)
    repo.save(documento)

    caso_de_uso = NormalizarDocumento(repo, _FakeNormalizationEngine(), [], _FakeOutputStore("06_normalizados"), _FakeAuditLogger())
    with pytest.raises(InvalidDocumentStateTransitionError):
        caso_de_uso.execute(documento.id)


def test_normalizar_documento_exitoso_guarda_en_carpeta_dedicada(tmp_path) -> None:
    repo = _FakeDocumentRepository()
    ruta_extraccion = tmp_path / "doc.md"
    ruta_extraccion.write_text("# Politica\n\nContenido revisado.", encoding="utf-8")
    documento = _documento_revisado(repo, ruta_extraccion=str(ruta_extraccion))

    engine = _FakeNormalizationEngine(cambios=["se elimino un pie de pagina"])
    output_store = _FakeOutputStore("06_normalizados")
    audit = _FakeAuditLogger()
    reglas = [ReglaNormalizacion(tipo_regla="colapsar_saltos_de_linea", parametros={})]
    caso_de_uso = NormalizarDocumento(repo, engine, reglas, output_store, audit)

    normalizado = caso_de_uso.execute(documento.id)

    assert normalizado.estado == EstadoDocumento.NORMALIZADO
    assert normalizado.cambios_normalizacion == ["se elimino un pie de pagina"]
    assert normalizado.ruta_normalizado in output_store.guardados
    assert output_store.guardados[normalizado.ruta_normalizado] == "# Politica\n\nContenido revisado. [normalizado]"
    assert engine.llamadas[0][1] == reglas
    assert [e.accion for e in audit.eventos] == ["normalizar_documento"]


def test_normalizar_documento_prefiere_el_markdown_corregido_sobre_el_extraido(tmp_path) -> None:
    """Modulo 8 (correccion): si el revisor guardo una correccion
    (ruta_revisado), NormalizarDocumento debe leer esa version, no la
    extraccion en crudo -- ver Documento.ruta_markdown_vigente()."""
    repo = _FakeDocumentRepository()
    ruta_extraccion = tmp_path / "doc.md"
    ruta_extraccion.write_text("# Politica\n\nContenido SIN corregir.", encoding="utf-8")
    ruta_revisado = tmp_path / "doc_revisado.md"
    ruta_revisado.write_text("# Politica\n\nContenido YA corregido.", encoding="utf-8")

    documento = _documento_revisado(repo, ruta_extraccion=str(ruta_extraccion))
    # _documento_revisado() ya avanzo hasta REVISADO -- para simular una
    # correccion hecha mientras el documento seguia EXTRAIDO, se
    # reconstruye el historico a mano en vez de llamar a corregir()
    # sobre un documento ya REVISADO (que fallaria por diseno: la
    # correccion solo es valida en EXTRAIDO).
    data = documento.model_dump()
    data["ruta_revisado"] = str(ruta_revisado)
    documento = Documento(**data)
    repo.save(documento)

    engine = _FakeNormalizationEngine()
    output_store = _FakeOutputStore("06_normalizados")
    caso_de_uso = NormalizarDocumento(repo, engine, [], output_store, _FakeAuditLogger())

    normalizado = caso_de_uso.execute(documento.id)
    assert output_store.guardados[normalizado.ruta_normalizado] == "# Politica\n\nContenido YA corregido. [normalizado]"


def test_normalizar_documento_fallido_no_deja_el_documento_atascado(tmp_path) -> None:
    # Mismo bug y mismo criterio que
    # test_extraer_documento_fallido_no_deja_el_documento_atascado_en_en_extraccion
    # en test_documents_service.py (encontrado 2026-07-29): un fallo del
    # motor de normalizacion no debe dejar el documento atascado en
    # EN_NORMALIZACION.
    repo = _FakeDocumentRepository()
    ruta_extraccion = tmp_path / "doc.md"
    ruta_extraccion.write_text("# Politica\n\nContenido revisado.", encoding="utf-8")
    documento = _documento_revisado(repo, ruta_extraccion=str(ruta_extraccion))

    engine = _FakeNormalizationEngine(excepcion=RuntimeError("regla de normalizacion invalida"))
    caso_de_uso = NormalizarDocumento(repo, engine, [], _FakeOutputStore("06_normalizados"), _FakeAuditLogger())

    with pytest.raises(RuntimeError):
        caso_de_uso.execute(documento.id)

    tras_el_fallo = repo.get(documento.id)
    assert tras_el_fallo.estado == EstadoDocumento.REVISADO

    engine.excepcion = None
    normalizado = caso_de_uso.execute(documento.id)
    assert normalizado.estado == EstadoDocumento.NORMALIZADO


def test_documents_service_normalizar_documento_sin_configurar_falla() -> None:
    from domain.documents.ports import DocumentExtractor, OriginalFileStore, PdfTextLayerDetector

    class _ExtractorMinimo(DocumentExtractor):
        def supports(self, formato, tipo_procesamiento):
            return True

        def extract(self, ruta, formato, tipo_procesamiento, on_progreso=None):
            from domain.documents.entities import ResultadoExtraccion

            return ResultadoExtraccion(markdown="x", metodo="x")

    class _FilesMinimo(OriginalFileStore):
        def copiar_original(self, ruta_origen):
            return "/proyecto/01_originales/x", _HASH_VALIDO, 1

    class _PdfMinimo(PdfTextLayerDetector):
        def tiene_capa_de_texto(self, ruta):
            return True

    service = DocumentsService(
        _FakeDocumentRepository(),
        _FilesMinimo(),
        _FakeAuditLogger(),
        _PdfMinimo(),
        _ExtractorMinimo(),
        _FakeOutputStore("03_extracciones"),
        revision_repository=_FakeRevisionRepository(),
        governance=_governance_sin_bloqueos(),
    )
    with pytest.raises(RuntimeError, match="Modulo 9"):
        service.normalizar_documento("cualquier-id")


class _RealFileOutputStore(ExtractionOutputStore):
    """A diferencia de _FakeOutputStore (en memoria), este si escribe a
    disco -- necesario aqui porque NormalizarDocumento lee el Markdown
    revisado desde su ruta real (Path.read_text()), igual que hace
    LocalExtractionOutputStore en produccion."""

    def __init__(self, carpeta) -> None:
        self.carpeta = carpeta
        self.carpeta.mkdir(parents=True, exist_ok=True)

    def guardar(self, documento_id: str, markdown: str) -> str:
        ruta = self.carpeta / f"{documento_id}.md"
        ruta.write_text(markdown, encoding="utf-8")
        return str(ruta)


def test_documents_service_normalizar_documento_configurado_usa_carpeta_dedicada(tmp_path) -> None:
    from domain.documents.entities import ResultadoExtraccion
    from domain.documents.ports import DocumentExtractor, OriginalFileStore, PdfTextLayerDetector

    class _ExtractorMinimo(DocumentExtractor):
        def supports(self, formato, tipo_procesamiento):
            return True

        def extract(self, ruta, formato, tipo_procesamiento, on_progreso=None):
            return ResultadoExtraccion(markdown="# Doc\n\ncontenido", metodo="x")

    class _FilesMinimo(OriginalFileStore):
        def copiar_original(self, ruta_origen):
            return "/proyecto/01_originales/x", _HASH_VALIDO, 1

    class _PdfMinimo(PdfTextLayerDetector):
        def tiene_capa_de_texto(self, ruta):
            return True

    repo = _FakeDocumentRepository()
    output_store = _RealFileOutputStore(tmp_path / "03_extracciones")
    normalized_store = _FakeOutputStore("06_normalizados")
    service = DocumentsService(
        repo,
        _FilesMinimo(),
        _FakeAuditLogger(),
        _PdfMinimo(),
        _ExtractorMinimo(),
        output_store,
        revision_repository=_FakeRevisionRepository(),
        governance=_governance_sin_bloqueos(),
        normalization_engine=_FakeNormalizationEngine(),
        reglas_normalizacion=[],
        normalized_output_store=normalized_store,
    )

    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")
    clasificado = service.clasificar_documento(documento.id)
    extraido = service.extraer_documento(clasificado.id)
    revisado = repo.get(extraido.id).avanzar_a(EstadoDocumento.EN_REVISION).avanzar_a(EstadoDocumento.REVISADO)
    repo.save(revisado)

    normalizado = service.normalizar_documento(revisado.id)
    assert normalizado.estado == EstadoDocumento.NORMALIZADO
    assert normalizado.ruta_normalizado in normalized_store.guardados
    # El normalizado debe quedar en 06_normalizados/ (normalized_store), nunca
    # mezclado en la carpeta de extraccion (output_store, aqui un directorio
    # real bajo tmp_path -- no tiene sentido buscar 'guardados' en el porque
    # no es un fake en memoria).
    assert str(output_store.carpeta) not in normalizado.ruta_normalizado
    assert normalizado.ruta_normalizado.startswith("/proyecto/06_normalizados/")
