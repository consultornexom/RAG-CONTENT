"""Bootstrap de la aplicacion (ADR-001, seccion 3: capa app).

Ensambla las implementaciones concretas de infrastructure detras de
los puertos de domain, y las entrega ya inyectadas a application -- ui
solo debe importar `ProjectsService`/`ProfilesService`/`DocumentsService`
desde aqui, nunca ensamblar nada por su cuenta (ADR-001, seccion 4: ui
depende solo de application).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.configuration import RutasAplicacion, cargar_rutas
from application.batches.service import BatchesService
from application.documents.service import DocumentsService
from application.governance.service import GovernanceService
from application.incidents.service import IncidentsService
from application.jobs.service import JobsService
from application.profiles.service import ProfilesService
from application.projects.service import ProjectsService
from application.reports.service import ReportsService
from application.security.service import SecurityService
from application.validity.service import ValidityService
from domain.acceptance.ports import InformeAceptacionWriter
from domain.projects.entities import Proyecto
from infrastructure.database.approval_repository import SqlAlchemyAprobacionRepository
from infrastructure.database.audit_logger import SqlAlchemyAuditLogger
from infrastructure.database.batch_repository import SqlAlchemyLoteRepository
from infrastructure.database.document_repository import SqlAlchemyDocumentRepository
from infrastructure.database.incident_repository import SqlAlchemyIncidentRepository
from infrastructure.database.engine import build_engine
from infrastructure.database.job_repository import SqlAlchemyTrabajoRepository
from infrastructure.database.migrations import RUTA_LINEA_GLOBAL, RUTA_LINEA_PROYECTO, upgrade_to_head
from infrastructure.database.project_content_checker import SqlAlchemyProjectContentChecker
from infrastructure.database.repository import SqlAlchemyProjectRepository
from infrastructure.database.revision_repository import SqlAlchemyRevisionRepository
from infrastructure.database.source_repository import SqlAlchemyFuenteRepository
from infrastructure.database.validity_repository import SqlAlchemyVigenciaRepository
from infrastructure.extraction.audio_video_transcription_extractor import AudioVideoTranscriptionExtractor
from infrastructure.extraction.composite_document_extractor import CompositeDocumentExtractor
from infrastructure.extraction.csv_extractor import CsvExtractor
from infrastructure.extraction.doc_legacy_extractor import DocLegacyExtractor
from infrastructure.extraction.docx_extractor import DocxExtractor
from infrastructure.extraction.faster_whisper_engine import FasterWhisperEngine
from infrastructure.extraction.image_ocr_extractor import ImageOcrExtractor
from infrastructure.extraction.json_extractor import JsonExtractor
from infrastructure.extraction.libreoffice_converter import LibreOfficeConverter
from infrastructure.extraction.pdf_extractor import PdfExtractor
from infrastructure.extraction.pdf_ocr_extractor import PdfOcrExtractor
from infrastructure.extraction.pypdf_text_layer_detector import PyPdfTextLayerDetector
from infrastructure.extraction.tesseract_ocr_engine import TesseractOcrEngine
from infrastructure.extraction.txt_markdown_extractor import TxtMarkdownExtractor
from infrastructure.extraction.xls_legacy_extractor import XlsLegacyExtractor
from infrastructure.extraction.xlsx_extractor import XlsxExtractor
from infrastructure.filesystem.csv_manifest_writer import CsvManifestWriter
from infrastructure.filesystem.entrega_rag_studio_store import LocalEntregaRagStudioStore
from infrastructure.filesystem.extraction_output_store import LocalExtractionOutputStore
from infrastructure.filesystem.local_report_writer import LocalReportWriter
from infrastructure.filesystem.markdown_informe_aceptacion_writer import MarkdownInformeAceptacionWriter
from infrastructure.filesystem.original_file_store import LocalOriginalFileStore
from infrastructure.filesystem.profile_loader import YamlProfileRepository
from infrastructure.filesystem.project_structure import LocalProjectFileStore
from infrastructure.normalization.rule_based_normalization_engine import RuleBasedNormalizationEngine
from infrastructure.security.encrypted_zip_respaldo_store import EncryptedZipRespaldoStore
from infrastructure.security.keyring_credential_store import KeyringCredentialStore
from workers.cola_de_trabajos import ColaDeTrabajos


@dataclass
class AppContext:
    rutas: RutasAplicacion
    session: Session
    projects: ProjectsService
    profiles: ProfilesService
    audit: SqlAlchemyAuditLogger


@dataclass
class ProjectContext:
    """Contexto de un proyecto abierto (proyecto.db propio, Documento
    Maestro seccion 4.5). Se obtiene siempre a traves de
    `abrir_proyecto()`, nunca ensamblando infrastructure directamente
    desde ui (ADR-001, seccion 4)."""

    session: Session
    documents: DocumentsService
    incidents: IncidentsService
    validity: ValidityService
    jobs: JobsService
    cola_trabajos: ColaDeTrabajos
    batches: BatchesService
    reports: ReportsService
    security: SecurityService
    # Hallazgo real de la cuarta auditoria general (2026-08-01):
    # `ui/panels/pruebas_panel.py` construia `MarkdownInformeAceptacionWriter`
    # directamente -- la unica excepcion en toda la capa `ui` al patron de
    # "los adaptadores de infrastructure se ensamblan una sola vez aqui,
    # ui solo los consume ya armados". `AcceptanceService` en si (Fase 9)
    # sigue construyendose bajo demanda en el panel y en
    # scripts/ejecutar_pruebas_aceptacion.py -- eso es deliberado, no
    # forma parte de este contexto (ver su propio docstring de modulo:
    # es una herramienta de QA de la herramienta misma, no un caso de
    # uso mas del proyecto abierto), pero el escritor de su informe si
    # pertenece a la carpeta del proyecto (`10_reportes/`), igual que
    # `report_writer`, asi que se ensambla aqui como el resto.
    informe_aceptacion_writer: InformeAceptacionWriter


def bootstrap(raiz: str | None = None) -> AppContext:
    """Punto de entrada unico de ensamblado. `raiz` explicito solo para
    pruebas (ver tests/smoke); en produccion resuelve segun
    `app.configuration.cargar_rutas()` (variable de entorno
    RAG_CONTENT_STUDIO_ROOT si esta definida, o una carpeta en el home
    del usuario -- ver su docstring para el bug real de 2026-07-30 que
    motivo este mecanismo)."""
    rutas = cargar_rutas(raiz)
    rutas.perfiles.mkdir(parents=True, exist_ok=True)
    rutas.proyectos.mkdir(parents=True, exist_ok=True)
    rutas.logs.mkdir(parents=True, exist_ok=True)

    upgrade_to_head(rutas.aplicacion_db, RUTA_LINEA_GLOBAL)
    engine = build_engine(rutas.aplicacion_db)
    session = sessionmaker(bind=engine, future=True)()

    repository = SqlAlchemyProjectRepository(session)
    audit = SqlAlchemyAuditLogger(session)
    profile_repository = YamlProfileRepository(rutas.perfiles)
    file_store = LocalProjectFileStore(rutas.proyectos)
    content_checker = SqlAlchemyProjectContentChecker()

    projects = ProjectsService(repository, profile_repository, file_store, audit, content_checker)
    profiles = ProfilesService(profile_repository)
    return AppContext(rutas=rutas, session=session, projects=projects, profiles=profiles, audit=audit)


def abrir_proyecto(ctx: AppContext, proyecto: Proyecto) -> ProjectContext:
    """Abre (creando si es la primera vez) la base proyecto.db del
    proyecto dado, dentro de su propia carpeta -- nunca comparte tablas
    con aplicacion.db (ver infrastructure.database.project_models).

    El registro de auditoria de Modulo 3 sigue escribiendo en la base
    global (`ctx.audit`, filtrable por proyecto_id) por consistencia
    con el Modulo 1 ya construido y probado; el ADR-001 (seccion 9)
    describe la auditoria como parte de proyecto.db a futuro -- se deja
    como desviacion conocida y documentada, no silenciosa, para no
    reabrir Modulo 1 dentro del alcance de Modulo 3."""
    carpeta = Path(proyecto.ruta_carpeta)
    db_path = carpeta / "proyecto.db"
    upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
    engine = build_engine(db_path)
    session = sessionmaker(bind=engine, future=True)()

    document_repository = SqlAlchemyDocumentRepository(session)
    original_file_store = LocalOriginalFileStore(carpeta / "01_originales")
    pdf_detector = PyPdfTextLayerDetector()
    ocr_engine = TesseractOcrEngine()
    legacy_converter = LibreOfficeConverter()
    transcription_engine = FasterWhisperEngine()
    extractor = CompositeDocumentExtractor(
        [
            TxtMarkdownExtractor(),
            JsonExtractor(),
            DocxExtractor(),
            PdfExtractor(),
            XlsxExtractor(),
            CsvExtractor(),
            DocLegacyExtractor(legacy_converter),
            XlsLegacyExtractor(legacy_converter),
            ImageOcrExtractor(ocr_engine),
            PdfOcrExtractor(ocr_engine),
            AudioVideoTranscriptionExtractor(transcription_engine),
        ]
    )
    output_store = LocalExtractionOutputStore(carpeta / "03_extracciones")
    transcription_output_store = LocalExtractionOutputStore(carpeta / "04_transcripciones")
    # Modulo 8 (correccion): carpeta propia para el Markdown corregido a
    # mano por el revisor, separada de 03_extracciones/ (que guarda la
    # extraccion en crudo, nunca modificada) -- ver Documento.corregir()
    # y Documento.ruta_markdown_vigente().
    correction_output_store = LocalExtractionOutputStore(carpeta / "05_revisiones")
    normalization_engine = RuleBasedNormalizationEngine()
    # Las reglas de normalizacion las define el perfil del proyecto
    # ("reglas en YAML por perfil", ADR-001 seccion 8) -- se resuelven
    # una sola vez aqui, no en cada llamada a normalizar_documento().
    # Si el perfil no existe (no deberia pasar: Modulo 1 lo valida al
    # crear el proyecto), se normaliza sin ninguna regla en vez de
    # fallar el arranque del proyecto entero por esto.
    perfil = ctx.profiles.obtener_perfil(proyecto.perfil_id)
    reglas_normalizacion = perfil.reglas_normalizacion if perfil is not None else []
    normalized_output_store = LocalExtractionOutputStore(carpeta / "06_normalizados")
    revision_repository = SqlAlchemyRevisionRepository(session)
    # Modulo 12 (Generador de Markdown): carpeta de entrega final,
    # separada de 06_normalizados/ (que es de trabajo interno) -- ver
    # Documento.generar_markdown() y el docstring de GenerarMarkdown.
    markdown_output_store = LocalExtractionOutputStore(carpeta / "07_markdown")
    aprobacion_repository = SqlAlchemyAprobacionRepository(session)
    # 12_exportaciones/: el manifiesto de entrega hacia RAG STUDIO
    # (seccion 4.6.1) -- ver GenerarManifiesto.
    manifest_writer = CsvManifestWriter(carpeta / "12_exportaciones")
    # 14_entrega_rag_studio/: agregado 2026-07-31 (comentario real del
    # consultor) -- consolida en una sola carpeta una copia del
    # manifiesto y de cada Markdown LIBERADO que referencia, ver
    # PrepararEntregaRagStudio.
    entrega_store = LocalEntregaRagStudioStore(carpeta / "14_entrega_rag_studio")

    # Modulo 10 (gestion de incidencias) se construye ANTES que
    # DocumentsService: Modulo 13 (governance, mas abajo) depende del
    # mismo IncidentRepository, y DocumentsService.revisar_documento()
    # depende de GovernanceService -- mismo reparto de responsabilidades
    # que RegistrarIncidencia (application.incidents) ya usa con
    # DocumentRepository, en sentido inverso. Incidencia.documento_id
    # referencia document_repository sin clave foranea -- RegistrarIncidencia
    # valida su existencia en application, no aqui. El registro de
    # auditoria de incidencias sigue la misma desviacion conocida que el
    # resto de este proyecto (ver parrafo de arriba sobre auditoria).
    incident_repository = SqlAlchemyIncidentRepository(session)
    incidents = IncidentsService(incident_repository, document_repository, ctx.audit)

    # Modulo 11 (Vigencias y fuentes): construido ANTES que
    # GovernanceService porque la segunda regla de Modulo 13 (mas abajo)
    # depende directamente de VigenciaRepository, ademas de
    # DocumentRepository.
    fuente_repository = SqlAlchemyFuenteRepository(session)
    vigencia_repository = SqlAlchemyVigenciaRepository(session)
    validity = ValidityService(fuente_repository, vigencia_repository, document_repository, ctx.audit)

    # Modulo 13 (Estados y dependencias): tres reglas reales -- no
    # aprobar con incidencias criticas todavia abiertas, ni un documento
    # critico con vigencia desconocida, ni liberar sin fuente y
    # aprobacion (Documento Maestro, seccion 4.7 y 8.2). Depende
    # directamente de IncidentRepository, VigenciaRepository,
    # DocumentRepository, FuenteRepository y AprobacionRepository, no de
    # sus fachadas -- ver los docstrings de
    # application.governance.verificar_documento_aprobable/
    # verificar_documento_liberable.
    governance = GovernanceService(
        incident_repository, vigencia_repository, document_repository, fuente_repository, aprobacion_repository
    )

    # Fase 7 (Lotes): se construye aqui, antes de DocumentsService, porque
    # GenerarManifiesto (dentro de DocumentsService, Modulo 12) tambien
    # depende de LoteRepository desde la cuarta auditoria general
    # (2026-08-01): valida que un `lote_id` exista antes de filtrar, en vez
    # de devolver un manifiesto vacio en silencio ante un typo -- mismo
    # puerto que ya usa BatchesService mas abajo, nunca dos instancias
    # separadas del repositorio.
    lote_repository = SqlAlchemyLoteRepository(session)

    documents = DocumentsService(
        document_repository,
        original_file_store,
        ctx.audit,
        pdf_detector,
        extractor,
        output_store,
        revision_repository,
        governance,
        transcription_output_store,
        normalization_engine,
        reglas_normalizacion,
        normalized_output_store,
        correction_output_store,
        aprobacion_repository,
        markdown_output_store,
        vigencia_repository,
        manifest_writer,
        entrega_store,
        lote_repository,
    )
    # Bug real encontrado 2026-07-29 (usuario sin Tesseract instalado):
    # antes de la correccion de ExtraerDocumento/NormalizarDocumento, un
    # fallo del extractor o del motor de normalizacion dejaba el
    # documento atascado en EN_EXTRACCION/EN_NORMALIZACION para siempre.
    # Esa correccion ya evita que vuelva a pasar, pero no repara, por si
    # sola, los documentos que un usuario ya tenia atascados en un
    # proyecto creado con una version anterior -- se recuperan aqui, UNA
    # SOLA VEZ al abrir el proyecto, mismo principio y mismo lugar que
    # jobs.recuperar_trabajos_interrumpidos() (ver
    # RecuperarDocumentosInterrumpidos).
    documents.recuperar_documentos_interrumpidos()

    # Fase 6 (Colas de trabajo y workers aislados): TrabajoRepository
    # depende de DocumentRepository (EncolarTrabajo valida que el
    # documento exista, mismo patron que RegistrarIncidencia). Se
    # recuperan los trabajos huerfanos (PREPARANDO/EJECUTANDO) UNA SOLA
    # VEZ al abrir el proyecto -- mismo principio de "el operador nunca
    # lo ejecuta a mano" que upgrade_to_head() -- antes de exponer
    # JobsService/ColaDeTrabajos a quien abra este ProjectContext, para
    # que nunca se vea un trabajo fantasma que ya no tiene ningun hilo
    # real corriendolo (ver RecuperarTrabajosInterrumpidos).
    trabajo_repository = SqlAlchemyTrabajoRepository(session)
    jobs = JobsService(trabajo_repository, document_repository, ctx.audit)
    jobs.recuperar_trabajos_interrumpidos()
    cola_trabajos = ColaDeTrabajos(jobs, documents)

    # Fase 7 (Lotes): BatchesService depende de DocumentRepository
    # directamente (AgregarDocumentoALote/QuitarDocumentoDeLote validan
    # el documento, mismo patron que EncolarTrabajo) y de
    # GovernanceService (CerrarLote reutiliza
    # verificar_documento_liberable() -- misma regla que LiberarDocumento,
    # nunca duplicada). `lote_repository` ya se construyo mas arriba,
    # antes de DocumentsService (ver comentario ahi).
    batches = BatchesService(lote_repository, document_repository, governance, ctx.audit)

    # Fase 8 (Reportes y documentacion automatica): ReportsService
    # depende directamente de TrabajoRepository/RevisionRepository/
    # IncidentRepository/AprobacionRepository/VigenciaRepository/
    # LoteRepository (los puertos de cada contexto, no sus fachadas) y
    # de GovernanceService (el informe de calidad reutiliza
    # verificar_documento_liberable(), misma regla que CerrarLote, nunca
    # duplicada) -- mismo criterio de acoplamiento cruzado que el resto
    # de este bootstrap. 10_reportes/: carpeta reservada desde la
    # Fase 1 (Documento Maestro, seccion 4.5) y sin uso real hasta ahora.
    report_writer = LocalReportWriter(carpeta / "10_reportes")
    reports = ReportsService(
        document_repository,
        vigencia_repository,
        trabajo_repository,
        revision_repository,
        incident_repository,
        aprobacion_repository,
        lote_repository,
        governance,
        report_writer,
    )

    # Fase 10 (Seguridad y distribucion): SecurityService no depende de
    # ningun repositorio de proyecto.db -- KeyringCredentialStore guarda
    # la clave de cifrado en el almacen de credenciales del sistema
    # operativo (fuera de cualquier base de datos propia, ADR-001
    # seccion 14.3) y EncryptedZipRespaldoStore trabaja directo sobre la
    # carpeta del proyecto en disco. No se audita en `ctx.audit` la
    # creacion/restauracion de respaldos (a diferencia del resto de
    # servicios de este bootstrap): el propio archivo cifrado en
    # 13_respaldos/, con su nombre con fecha, ya es su propio rastro --
    # agregar un tipo de evento de auditoria nuevo solo para esto queda
    # fuera del alcance minimo de esta fase (seccion 9 del Documento
    # Maestro no lo exige de forma explicita).
    security = SecurityService(KeyringCredentialStore(), EncryptedZipRespaldoStore())

    # Fase 9 (Pruebas de aceptacion): mismo criterio que report_writer --
    # se ensambla aqui, una sola vez, en vez de en ui/panels/pruebas_panel.py
    # (hallazgo real de la cuarta auditoria general, ver comentario en
    # ProjectContext).
    informe_aceptacion_writer = MarkdownInformeAceptacionWriter(carpeta / "10_reportes")

    return ProjectContext(
        session=session,
        documents=documents,
        incidents=incidents,
        validity=validity,
        jobs=jobs,
        cola_trabajos=cola_trabajos,
        batches=batches,
        reports=reports,
        security=security,
        informe_aceptacion_writer=informe_aceptacion_writer,
    )
