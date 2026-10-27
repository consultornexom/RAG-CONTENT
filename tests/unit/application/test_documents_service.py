from __future__ import annotations

import pytest

from application.documents.service import DocumentsService
from application.governance.service import GovernanceService
from domain.audit.entities import EventoAuditoria
from domain.documents.entities import Documento, EstadoDocumento, ResultadoExtraccion
from domain.documents.exceptions import (
    CorreccionRequiereEstadoExtraidoError,
    DocumentNotFoundError,
    DuplicateDocumentHashError,
    PdfIllegibleError,
    UnsupportedExtractionRouteError,
    UnsupportedFormatError,
)
from domain.documents.ports import (
    AprobacionRepository,
    DocumentExtractor,
    DocumentRepository,
    ExtractionOutputStore,
    OriginalFileStore,
    PdfTextLayerDetector,
    RevisionRepository,
)
from domain.incidents.ports import IncidentRepository
from domain.projects.ports import AuditLogger
from domain.validity.ports import FuenteRepository, VigenciaRepository


class _FakeDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._por_id: dict[str, Documento] = {}

    def save(self, documento):
        self._por_id[documento.id] = documento

    def get(self, documento_id):
        return self._por_id.get(documento_id)

    def get_by_hash(self, hash_sha256):
        return next((d for d in self._por_id.values() if d.hash_sha256 == hash_sha256), None)

    def list_by_estado(self, estado):
        return [d for d in self._por_id.values() if d.estado == estado]

    def list(self):
        return list(self._por_id.values())


class _FakeRevisionRepository(RevisionRepository):
    def __init__(self) -> None:
        self.guardadas: list = []

    def save(self, revision) -> None:
        self.guardadas.append(revision)

    def list_by_document(self, documento_id: str):
        return [r for r in self.guardadas if r.documento_id == documento_id]


class _FakeIncidentRepository(IncidentRepository):
    """Sin incidencias por defecto -- suficiente para construir un
    GovernanceService (Modulo 13) que nunca bloquea en estas pruebas,
    que no ejercitan la regla de incidencias criticas (ver
    test_revisar_documento.py para esa)."""

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
    segunda regla de Modulo 13 (ver test_revisar_documento.py para esa);
    como el `DocumentRepository` que se le pasa a `GovernanceService`
    aqui esta siempre vacio, `documento.get()` regresa None y la regla
    se salta sin importar el contenido de este repositorio."""

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


class _FakeOriginalFileStore(OriginalFileStore):
    """Simula la copia sin tocar el disco -- el hash lo decide la
    prueba para poder provocar duplicados a voluntad."""

    def __init__(self, hash_fijo: str = "b" * 64, tamano_fijo: int = 2048):
        self.hash_fijo = hash_fijo
        self.tamano_fijo = tamano_fijo
        self.llamadas: list[str] = []

    def copiar_original(self, ruta_origen: str):
        self.llamadas.append(ruta_origen)
        return f"/proyecto/01_originales/{self.hash_fijo[:12]}_archivo", self.hash_fijo, self.tamano_fijo


class _FakePdfTextLayerDetector(PdfTextLayerDetector):
    """Por defecto simula un PDF con texto (no ambiguo). Las pruebas
    de clasificacion ajustan `resultado` o `excepcion` a voluntad."""

    def __init__(self, resultado: bool = True, excepcion: Exception | None = None):
        self.resultado = resultado
        self.excepcion = excepcion

    def tiene_capa_de_texto(self, ruta: str) -> bool:
        if self.excepcion is not None:
            raise self.excepcion
        return self.resultado


class _FakeDocumentExtractor(DocumentExtractor):
    def __init__(
        self,
        markdown: str = "# Titulo\n\ncontenido",
        metodo: str = "docx",
        advertencias=None,
        excepcion: Exception | None = None,
    ):
        self.markdown = markdown
        self.metodo = metodo
        self.advertencias = advertencias or []
        self.llamadas: list[str] = []
        # Permite simular un fallo real del motor de extraccion (ej.
        # Tesseract/LibreOffice no instalado) sin tener que instalarlo
        # de verdad -- ver test_extraer_documento_fallido_no_deja_*.
        self.excepcion = excepcion
        # Corregido 2026-07-31: registra las llamadas a on_progreso que
        # DocumentsService.extraer_documento() reenvia -- ver
        # test_extraer_documento_reenvia_on_progreso_al_extractor.
        self.llamadas_on_progreso: list[tuple[int, int]] = []

    def supports(self, formato, tipo_procesamiento) -> bool:
        return True

    def extract(self, ruta: str, formato, tipo_procesamiento, on_progreso=None) -> ResultadoExtraccion:
        self.llamadas.append(ruta)
        if on_progreso is not None:
            on_progreso(1, 1)
            self.llamadas_on_progreso.append((1, 1))
        if self.excepcion is not None:
            raise self.excepcion
        return ResultadoExtraccion(markdown=self.markdown, metodo=self.metodo, advertencias=self.advertencias)


class _FakeExtractionOutputStore(ExtractionOutputStore):
    def __init__(self, carpeta: str = "03_extracciones") -> None:
        self.carpeta = carpeta
        self.guardados: dict[str, str] = {}

    def guardar(self, documento_id: str, markdown: str) -> str:
        ruta = f"/proyecto/{self.carpeta}/{documento_id}.md"
        self.guardados[ruta] = markdown
        return ruta


class _FakeAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    def record(self, proyecto_id, accion, valor_anterior, valor_nuevo, motivo):
        self.eventos.append(
            EventoAuditoria(
                proyecto_id=proyecto_id,
                accion=accion,
                valor_anterior=valor_anterior,
                valor_nuevo=valor_nuevo,
                motivo=motivo,
            )
        )

    def list_by_project(self, proyecto_id):
        return [e for e in self.eventos if e.proyecto_id == proyecto_id]


@pytest.fixture()
def entorno():
    files = _FakeOriginalFileStore()
    audit = _FakeAuditLogger()
    pdf_detector = _FakePdfTextLayerDetector()
    extractor = _FakeDocumentExtractor()
    output_store = _FakeExtractionOutputStore()
    service = DocumentsService(
        _FakeDocumentRepository(),
        files,
        audit,
        pdf_detector,
        extractor,
        output_store,
        revision_repository=_FakeRevisionRepository(),
        governance=_governance_sin_bloqueos(),
    )
    return service, files, audit, pdf_detector, extractor, output_store


def test_registrar_documento_lo_deja_inventariado(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")

    assert documento.estado.value == "inventariado"
    assert documento.nombre_original == "politica.pdf"
    assert service.obtener_documento(documento.id) is not None


def test_registrar_documento_deja_evento_de_auditoria(entorno) -> None:
    service, _files, audit, _pdf, _extractor, _output = entorno
    service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")

    assert len(audit.eventos) == 1
    assert audit.eventos[0].accion == "registrar_documento"


def test_registrar_documento_con_hash_duplicado_falla(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")

    with pytest.raises(DuplicateDocumentHashError):
        service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica_copia.pdf")


def test_registrar_documento_con_extension_no_admitida_falla(entorno) -> None:
    # .avi no esta en la lista confirmada (seccion 4.4): solo MP3/WAV/M4A
    # (audio) y MP4/MOV (video) entraron a la primera version (Modulo 7).
    service, _files, _audit, _pdf, _extractor, _output = entorno
    with pytest.raises(UnsupportedFormatError):
        service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/video.avi")

    # No debe intentar copiar un archivo cuyo formato ya se sabe que no se admite.
    assert _files.llamadas == []


def test_buscar_por_hash_encuentra_el_documento_registrado(entorno) -> None:
    service, files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")

    encontrado = service.buscar_por_hash(files.hash_fijo)
    assert encontrado is not None
    assert encontrado.id == documento.id


def test_clasificar_documento_pdf_con_texto_va_a_extraccion_directa(entorno) -> None:
    service, _files, _audit, pdf_detector, _extractor, _output = entorno
    pdf_detector.resultado = True
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.estado.value == "clasificado"
    assert clasificado.tipo_procesamiento.value == "extraccion_directa"


def test_clasificar_documento_pdf_sin_texto_va_a_ocr(entorno) -> None:
    service, _files, _audit, pdf_detector, _extractor, _output = entorno
    pdf_detector.resultado = False
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/escaneado.pdf")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "ocr"


def test_clasificar_documento_pdf_illegible_va_a_correccion_manual(entorno) -> None:
    service, _files, _audit, pdf_detector, _extractor, _output = entorno
    pdf_detector.excepcion = PdfIllegibleError("/tmp/x/roto.pdf", "cifrado")
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/roto.pdf")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "correccion_manual"


def test_clasificar_documento_imagen_va_siempre_a_ocr(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/pagina.png")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "ocr"


def test_clasificar_documento_audio_va_siempre_a_transcripcion(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/entrevista.mp3")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "transcripcion"


def test_clasificar_documento_video_va_siempre_a_transcripcion(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/reunion.mp4")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "transcripcion"


def test_clasificar_documento_docx_va_a_extraccion_directa(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/contrato.docx")

    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "extraccion_directa"


def test_clasificar_documento_inexistente_falla(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    with pytest.raises(DocumentNotFoundError):
        service.clasificar_documento("no-existe")


def test_clasificar_documento_deja_evento_de_auditoria(entorno) -> None:
    service, _files, audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")
    service.clasificar_documento(documento.id)

    acciones = [e.accion for e in audit.eventos]
    assert acciones == ["registrar_documento", "clasificar_documento"]


def _registrar_y_clasificar(service, ruta_origen: str = "/tmp/x/contrato.docx"):
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen=ruta_origen)
    return service.clasificar_documento(documento.id)


def test_extraer_documento_lo_deja_extraido(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    clasificado = _registrar_y_clasificar(service)

    extraido = service.extraer_documento(clasificado.id)
    assert extraido.estado.value == "extraido"
    assert extraido.ruta_extraccion is not None
    assert extraido.ruta_extraccion in _output.guardados


def test_extraer_documento_reenvia_on_progreso_al_extractor(entorno) -> None:
    """Corregido 2026-07-31 (captura real del consultor: dialogo de
    progreso en negro con los botones nativos de Windows "Forzar la
    salida"/"Esperar" durante el OCR de un solo documento):
    `DocumentsService.extraer_documento()` debe reenviar `on_progreso`
    sin tocar hasta el extractor concreto -- ver domain.documents.ports.
    DocumentExtractor.extract() y ui.wizard.etapas.EtapaProcesar."""
    service, _files, _audit, _pdf, extractor, _output = entorno
    clasificado = _registrar_y_clasificar(service)

    llamadas: list[tuple[int, int]] = []
    service.extraer_documento(clasificado.id, on_progreso=lambda pagina, total: llamadas.append((pagina, total)))
    assert llamadas == [(1, 1)]
    assert extractor.llamadas_on_progreso == [(1, 1)]


def test_extraer_documento_guarda_el_markdown_producido(entorno) -> None:
    service, _files, _audit, _pdf, extractor, output = entorno
    extractor.markdown = "# Contrato\n\ncontenido de prueba"
    clasificado = _registrar_y_clasificar(service)

    extraido = service.extraer_documento(clasificado.id)
    assert output.guardados[extraido.ruta_extraccion] == "# Contrato\n\ncontenido de prueba"


def test_extraer_documento_guarda_las_advertencias() -> None:
    files = _FakeOriginalFileStore()
    audit = _FakeAuditLogger()
    pdf_detector = _FakePdfTextLayerDetector()
    extractor = _FakeDocumentExtractor(advertencias=["la pagina 2 no produjo texto"])
    output = _FakeExtractionOutputStore()
    service = DocumentsService(
        _FakeDocumentRepository(),
        files,
        audit,
        pdf_detector,
        extractor,
        output,
        revision_repository=_FakeRevisionRepository(),
        governance=_governance_sin_bloqueos(),
    )

    clasificado = _registrar_y_clasificar(service)
    extraido = service.extraer_documento(clasificado.id)
    assert extraido.advertencias_extraccion == ["la pagina 2 no produjo texto"]


def test_extraer_documento_clasificado_como_ocr_ya_no_falla(entorno) -> None:
    # Modulo 6: a diferencia de Modulo 5 (donde OCR se rechazaba con
    # UnsupportedExtractionRouteError), la ruta OCR ahora es valida --
    # quien procesa realmente el archivo es ImageOcrExtractor/
    # PdfOcrExtractor (ver test_ocr_extractors.py), no este fake.
    service, _files, _audit, pdf_detector, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/pagina.png")
    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "ocr"

    extraido = service.extraer_documento(clasificado.id)
    assert extraido.estado.value == "extraido"


def test_extraer_documento_de_transcripcion_usa_carpeta_dedicada_04() -> None:
    # A diferencia de extraccion directa/OCR (03_extracciones/), una
    # transcripcion debe guardarse en 04_transcripciones/ -- carpeta ya
    # reservada desde el Modulo 1 (Documento Maestro, seccion 4.5).
    # Se construye un DocumentsService propio (no el de la fixture
    # `entorno`) para poder pasar dos ExtractionOutputStore distintos y
    # verificar que ExtraerDocumento elige el correcto segun la ruta.
    files = _FakeOriginalFileStore()
    audit = _FakeAuditLogger()
    pdf_detector = _FakePdfTextLayerDetector()
    extractor = _FakeDocumentExtractor()
    output_store = _FakeExtractionOutputStore(carpeta="03_extracciones")
    transcription_output_store = _FakeExtractionOutputStore(carpeta="04_transcripciones")
    service = DocumentsService(
        _FakeDocumentRepository(),
        files,
        audit,
        pdf_detector,
        extractor,
        output_store,
        revision_repository=_FakeRevisionRepository(),
        governance=_governance_sin_bloqueos(),
        transcription_output_store=transcription_output_store,
    )

    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/entrevista.mp3")
    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "transcripcion"

    extraido = service.extraer_documento(clasificado.id)
    assert extraido.ruta_extraccion in transcription_output_store.guardados
    assert extraido.ruta_extraccion not in output_store.guardados
    assert "/04_transcripciones/" in extraido.ruta_extraccion


def test_extraer_documento_clasificado_como_transcripcion_ya_no_falla(entorno) -> None:
    # Modulo 7: la ruta TRANSCRIPCION tambien es valida ahora -- quien
    # procesa realmente el archivo es AudioVideoTranscriptionExtractor
    # (ver test_transcription_extractor.py), no este fake.
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/entrevista.mp3")
    clasificado = service.clasificar_documento(documento.id)
    assert clasificado.tipo_procesamiento.value == "transcripcion"

    extraido = service.extraer_documento(clasificado.id)
    assert extraido.estado.value == "extraido"


def test_extraer_documento_clasificado_como_correccion_manual_falla(entorno) -> None:
    from domain.documents.entities import TipoProcesamiento

    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/roto.pdf")
    # No hay un flujo publico que produzca CORRECCION_MANUAL en este
    # fake de pruebas (el real es PdfIllegibleError en clasificar), asi
    # que se fija directo sobre el repositorio para aislar el chequeo
    # de ExtraerDocumento en si.
    repo = service._repository  # type: ignore[attr-defined]
    pendiente = repo.get(documento.id)
    corregido = pendiente.clasificar(TipoProcesamiento.CORRECCION_MANUAL)
    repo.save(corregido)

    with pytest.raises(UnsupportedExtractionRouteError):
        service.extraer_documento(documento.id)


def test_extraer_documento_inexistente_falla(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    with pytest.raises(DocumentNotFoundError):
        service.extraer_documento("no-existe")


def test_extraer_documento_sin_clasificar_falla(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    documento = service.registrar_documento(proyecto_id="PROY-0001", ruta_origen="/tmp/x/politica.pdf")

    with pytest.raises(UnsupportedExtractionRouteError):
        service.extraer_documento(documento.id)


def test_extraer_documento_deja_evento_de_auditoria(entorno) -> None:
    service, _files, audit, _pdf, _extractor, _output = entorno
    clasificado = _registrar_y_clasificar(service)
    service.extraer_documento(clasificado.id)

    acciones = [e.accion for e in audit.eventos]
    assert acciones == ["registrar_documento", "clasificar_documento", "extraer_documento"]


def test_extraer_documento_fallido_no_deja_el_documento_atascado_en_en_extraccion(entorno) -> None:
    # Bug real reportado por un usuario (2026-07-29): sin OCR instalado
    # (Tesseract), la extraccion fallaba y el documento quedaba "en_extraccion"
    # para siempre -- ExtraerDocumento.execute() guarda ese estado
    # intermedio ANTES de invocar al extractor real, y si el extractor
    # lanza una excepcion no habia ningun rollback. El reintento
    # posterior (incluso ya con Tesseract instalado) fallaba entonces con
    # InvalidDocumentStateTransitionError: "no se permite pasar de
    # 'en_extraccion' a 'en_extraccion'" -- el propio chequeo de "marcar
    # en extraccion" del reintento rechazaba la transicion porque el
    # documento ya estaba ahi. El documento quedaba atascado sin ninguna
    # forma de recuperarlo desde la interfaz.
    service, _files, _audit, _pdf, extractor, _output = entorno
    clasificado = _registrar_y_clasificar(service)
    extractor.excepcion = RuntimeError("TesseractNotFoundError: el binario 'tesseract' no esta instalado")

    with pytest.raises(RuntimeError):
        service.extraer_documento(clasificado.id)

    # El documento debe volver a su estado anterior (clasificado), no
    # quedar atascado en "en_extraccion".
    tras_el_fallo = service.obtener_documento(clasificado.id)
    assert tras_el_fallo.estado.value == "clasificado"

    # Una vez resuelto el problema de fondo (Tesseract instalado), el
    # reintento debe funcionar sin necesitar ninguna intervencion manual.
    extractor.excepcion = None
    extraido = service.extraer_documento(clasificado.id)
    assert extraido.estado.value == "extraido"


def test_recuperar_documentos_interrumpidos_revierte_documentos_ya_atascados(entorno) -> None:
    # Complemento del test anterior: ese cubre que un fallo NUEVO ya no
    # deja atascado el documento; este cubre que un documento que YA
    # estaba atascado en EN_EXTRACCION -- por ejemplo, en un proyecto
    # creado con una version de la aplicacion anterior a esta correccion
    # (2026-07-29) -- se repara solo al reabrir el proyecto, sin que el
    # usuario tenga que hacer nada manual (ver
    # app.bootstrap.abrir_proyecto(), que llama a este metodo una sola
    # vez cada vez que se abre un proyecto, igual que
    # jobs.recuperar_trabajos_interrumpidos()).
    service, _files, audit, _pdf, _extractor, _output = entorno
    clasificado = _registrar_y_clasificar(service)
    repo = service._repository  # type: ignore[attr-defined]
    atascado = repo.get(clasificado.id).avanzar_a(EstadoDocumento.EN_EXTRACCION)
    repo.save(atascado)

    recuperados = service.recuperar_documentos_interrumpidos()

    assert [d.id for d in recuperados] == [clasificado.id]
    assert repo.get(clasificado.id).estado.value == "clasificado"
    assert audit.eventos[-1].accion == "recuperar_documento_interrumpido"

    # Y una vez recuperado, el documento vuelve a ser retomable sin
    # ninguna intervencion manual.
    extraido = service.extraer_documento(clasificado.id)
    assert extraido.estado.value == "extraido"


def test_recuperar_documentos_interrumpidos_no_hace_nada_si_no_hay_atascados(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    _registrar_y_clasificar(service)

    assert service.recuperar_documentos_interrumpidos() == []


def test_corregir_extraccion_guarda_ruta_revisado_sin_avanzar_estado(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, output = entorno
    clasificado = _registrar_y_clasificar(service)
    extraido = service.extraer_documento(clasificado.id)

    corregido = service.corregir_extraccion(extraido.id, "# Markdown corregido a mano")
    assert corregido.estado.value == "extraido"
    assert corregido.ruta_revisado is not None
    assert output.guardados[corregido.ruta_revisado] == "# Markdown corregido a mano"


def test_corregir_extraccion_documento_inexistente_falla(entorno) -> None:
    service, _files, _audit, _pdf, _extractor, _output = entorno
    with pytest.raises(DocumentNotFoundError):
        service.corregir_extraccion("no-existe", "contenido")


def test_corregir_extraccion_en_estado_invalido_no_escribe_nada(entorno) -> None:
    """Hallazgo real de la cuarta auditoria general (2026-08-01): antes de
    este fix, `CorregirExtraccion.execute()` llamaba a
    `output_store.guardar()` ANTES de que `documento.corregir()` validara
    `estado == EXTRAIDO` -- invocarlo sobre un documento en cualquier otro
    estado (aqui, recien CLASIFICADO, antes de extraer) ya dejaba un
    archivo escrito en el store antes del rechazo. Esta prueba confirma
    tanto la excepcion correcta como que el store queda vacio."""
    service, _files, _audit, _pdf, _extractor, output = entorno
    clasificado = _registrar_y_clasificar(service)
    assert clasificado.estado == EstadoDocumento.CLASIFICADO

    with pytest.raises(CorreccionRequiereEstadoExtraidoError):
        service.corregir_extraccion(clasificado.id, "contenido que no deberia guardarse")

    assert output.guardados == {}


def test_corregir_extraccion_deja_evento_de_auditoria(entorno) -> None:
    service, _files, audit, _pdf, _extractor, _output = entorno
    clasificado = _registrar_y_clasificar(service)
    extraido = service.extraer_documento(clasificado.id)
    service.corregir_extraccion(extraido.id, "contenido corregido")

    acciones = [e.accion for e in audit.eventos]
    assert acciones[-1] == "corregir_extraccion"


def test_corregir_extraccion_usa_carpeta_dedicada_05_si_se_configura() -> None:
    # A diferencia de la extraccion en crudo (03_extracciones/), una
    # correccion humana debe poder guardarse en su propia carpeta
    # dedicada (05_revisiones/) cuando quien construye el servicio pasa
    # un correction_output_store explicito -- mismo patron que
    # transcription_output_store (04_transcripciones/) ya usa.
    files = _FakeOriginalFileStore()
    audit = _FakeAuditLogger()
    pdf_detector = _FakePdfTextLayerDetector()
    extractor = _FakeDocumentExtractor()
    output_store = _FakeExtractionOutputStore(carpeta="03_extracciones")
    correction_output_store = _FakeExtractionOutputStore(carpeta="05_revisiones")
    service = DocumentsService(
        _FakeDocumentRepository(),
        files,
        audit,
        pdf_detector,
        extractor,
        output_store,
        revision_repository=_FakeRevisionRepository(),
        governance=_governance_sin_bloqueos(),
        correction_output_store=correction_output_store,
    )

    clasificado = _registrar_y_clasificar(service)
    extraido = service.extraer_documento(clasificado.id)
    corregido = service.corregir_extraccion(extraido.id, "contenido corregido")

    assert corregido.ruta_revisado in correction_output_store.guardados
    assert corregido.ruta_revisado not in output_store.guardados
    assert "/05_revisiones/" in corregido.ruta_revisado
