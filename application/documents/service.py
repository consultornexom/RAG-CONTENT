"""Fachada del contexto Documentos (ADR-001, seccion 4: ui solo depende
de application)."""
from __future__ import annotations

from collections.abc import Callable

from application.governance.service import GovernanceService
from domain.batches.ports import LoteRepository
from domain.documents.entities import Aprobacion, Criticidad, Documento, Prioridad, Revision
from domain.documents.ports import (
    AprobacionRepository,
    DocumentExtractor,
    DocumentRepository,
    EntregaRagStudioStore,
    ExtractionOutputStore,
    ManifestWriter,
    NormalizationEngine,
    OriginalFileStore,
    PdfTextLayerDetector,
    RevisionRepository,
)
from domain.profiles.entities import ReglaNormalizacion
from domain.projects.ports import AuditLogger
from domain.validity.ports import VigenciaRepository

from .commands.aprobar_para_markdown import AprobarParaMarkdown
from .commands.clasificar_documento import ClasificarDocumento
from .commands.corregir_extraccion import CorregirExtraccion
from .commands.extraer_documento import ExtraerDocumento
from .commands.generar_manifiesto import GenerarManifiesto
from .commands.generar_markdown import GenerarMarkdown
from .commands.liberar_documento import LiberarDocumento
from .commands.normalizar_documento import NormalizarDocumento
from .commands.preparar_entrega_rag_studio import PrepararEntregaRagStudio
from .commands.recuperar_documentos_interrumpidos import RecuperarDocumentosInterrumpidos
from .commands.registrar_documento import RegistrarDocumento
from .commands.revisar_documento import RevisarDocumento
from .commands.validar_markdown import ValidarMarkdown


class DocumentsService:
    def __init__(
        self,
        repository: DocumentRepository,
        files: OriginalFileStore,
        audit: AuditLogger,
        pdf_detector: PdfTextLayerDetector,
        extractor: DocumentExtractor,
        output_store: ExtractionOutputStore,
        revision_repository: RevisionRepository,
        governance: GovernanceService,
        transcription_output_store: ExtractionOutputStore | None = None,
        normalization_engine: NormalizationEngine | None = None,
        reglas_normalizacion: list[ReglaNormalizacion] | None = None,
        normalized_output_store: ExtractionOutputStore | None = None,
        correction_output_store: ExtractionOutputStore | None = None,
        aprobacion_repository: AprobacionRepository | None = None,
        markdown_output_store: ExtractionOutputStore | None = None,
        vigencia_repository: VigenciaRepository | None = None,
        manifest_writer: ManifestWriter | None = None,
        entrega_store: EntregaRagStudioStore | None = None,
        lote_repository: LoteRepository | None = None,
    ):
        self._repository = repository
        self._revision_repository = revision_repository
        self._registrar = RegistrarDocumento(repository, files, audit)
        self._clasificar = ClasificarDocumento(repository, pdf_detector, audit)
        self._extraer = ExtraerDocumento(repository, extractor, output_store, audit, transcription_output_store)
        self._revisar = RevisarDocumento(repository, revision_repository, audit, governance)
        # Modulo 8 (correccion): reusa output_store (03_extracciones/)
        # por defecto si quien construye el servicio no pasa uno propio
        # -- app.bootstrap si pasa uno dedicado, apuntado a
        # 05_revisiones/ (mismo patron que transcription_output_store).
        self._corregir = CorregirExtraccion(repository, correction_output_store or output_store, audit)
        # Bug real 2026-07-29 (usuario sin Tesseract): recupera documentos
        # que hayan quedado atascados en EN_EXTRACCION/EN_NORMALIZACION por
        # un fallo previo a la correccion de ExtraerDocumento/
        # NormalizarDocumento -- mismo principio que
        # JobsService._recuperar_interrumpidos, invocado una sola vez al
        # abrir el proyecto (ver app.bootstrap.abrir_proyecto()).
        self._recuperar_interrumpidos = RecuperarDocumentosInterrumpidos(repository, audit)
        # Modulo 9: solo se ensambla si quien construye el servicio pasa
        # tanto el motor como el store de salida -- app.bootstrap siempre
        # los pasa; las pruebas que no ejercitan normalizacion pueden
        # seguir construyendo DocumentsService sin ellos (ver
        # normalizar_documento(), que falla con un mensaje claro si se
        # llama sin haberlos configurado).
        self._normalizar: NormalizarDocumento | None = None
        if normalization_engine is not None and normalized_output_store is not None:
            self._normalizar = NormalizarDocumento(
                repository, normalization_engine, reglas_normalizacion or [], normalized_output_store, audit
            )
        # Modulo 12 (Generador de Markdown) + Modulo 13 (tercera regla):
        # mismo criterio que Modulo 9 -- solo se ensambla si quien
        # construye el servicio pasa las dependencias nuevas; las
        # pruebas que no ejercitan este tramo del flujo (todo lo previo
        # a NORMALIZADO) pueden seguir construyendo DocumentsService sin
        # ellas.
        self._aprobacion_repository = aprobacion_repository
        self._aprobar_para_markdown: AprobarParaMarkdown | None = None
        self._generar_markdown: GenerarMarkdown | None = None
        self._liberar_documento: LiberarDocumento | None = None
        self._generar_manifiesto: GenerarManifiesto | None = None
        # Agregado 2026-07-31 (comentario real del consultor): solo se
        # ensambla si ADEMAS se paso entrega_store -- mismo criterio que
        # el resto de este bloque; requiere que _generar_manifiesto
        # tambien se haya podido construir (se resuelve mas abajo, una
        # vez que ese if ya corrio).
        self._preparar_entrega_rag_studio: PrepararEntregaRagStudio | None = None
        if aprobacion_repository is not None:
            self._aprobar_para_markdown = AprobarParaMarkdown(repository, aprobacion_repository, audit, governance)
            self._liberar_documento = LiberarDocumento(repository, audit, governance)
        if markdown_output_store is not None:
            self._generar_markdown = GenerarMarkdown(repository, markdown_output_store, audit)
        # Validar_markdown solo depende de DocumentRepository/AuditLogger
        # (ya obligatorios en este servicio) -- siempre disponible, a
        # diferencia de las otras piezas nuevas de este modulo.
        self._validar_markdown = ValidarMarkdown(repository, audit)
        # Hallazgo real de la cuarta auditoria general (2026-08-01):
        # GenerarManifiesto ahora depende tambien de LoteRepository (valida
        # que lote_id exista antes de filtrar, en vez de devolver un
        # manifiesto vacio en silencio ante un typo) -- por eso este bloque
        # ahora tambien exige lote_repository, ademas de vigencia_repository
        # y manifest_writer, para poder ensamblarse.
        if vigencia_repository is not None and manifest_writer is not None and lote_repository is not None:
            self._generar_manifiesto = GenerarManifiesto(repository, lote_repository, vigencia_repository, manifest_writer)
            if entrega_store is not None:
                # lote_repository ya es obligatorio para entrar a este
                # bloque (condicion del `if` de arriba) -- se le pasa
                # tambien a PrepararEntregaRagStudio, que lo necesita
                # ADEMAS para leer el nombre del lote al entregar uno
                # especifico (2026-10-03, entregas separadas por lote con
                # version).
                self._preparar_entrega_rag_studio = PrepararEntregaRagStudio(
                    repository, self._generar_manifiesto, entrega_store, lote_repository
                )

    def registrar_documento(
        self,
        proyecto_id: str,
        ruta_origen: str,
        metadatos: dict[str, str] | None = None,
        prioridad: Prioridad = Prioridad.NORMAL,
        criticidad: Criticidad = Criticidad.NO_CRITICO,
    ) -> Documento:
        return self._registrar.execute(
            proyecto_id=proyecto_id,
            ruta_origen=ruta_origen,
            metadatos=metadatos,
            prioridad=prioridad,
            criticidad=criticidad,
        )

    def clasificar_documento(self, documento_id: str) -> Documento:
        return self._clasificar.execute(documento_id)

    def extraer_documento(
        self, documento_id: str, on_progreso: Callable[[int, int], None] | None = None
    ) -> Documento:
        # on_progreso: callback opcional (pagina_actual, total_paginas)
        # para OCR de PDF -- ver docstring de domain.documents.ports.
        # DocumentExtractor.extract() y de ui.wizard.etapas.
        # EtapaProcesar._on_procesar() para el porque (2026-07-31).
        return self._extraer.execute(documento_id, on_progreso)

    def corregir_extraccion(self, documento_id: str, markdown_corregido: str) -> Documento:
        return self._corregir.execute(documento_id, markdown_corregido)

    def revisar_documento(
        self,
        documento_id: str,
        revisor: str,
        comentario: str = "",
        incidencias_detectadas: list[str] | None = None,
    ) -> Documento:
        return self._revisar.execute(documento_id, revisor, comentario, incidencias_detectadas)

    def listar_revisiones(self, documento_id: str) -> list[Revision]:
        return self._revision_repository.list_by_document(documento_id)

    def normalizar_documento(self, documento_id: str) -> Documento:
        if self._normalizar is None:
            raise RuntimeError(
                "Modulo 9 (normalizacion) no esta configurado en este DocumentsService -- "
                "faltan normalization_engine y/o normalized_output_store al construirlo."
            )
        return self._normalizar.execute(documento_id)

    def obtener_documento(self, documento_id: str) -> Documento | None:
        return self._repository.get(documento_id)

    def buscar_por_hash(self, hash_sha256: str) -> Documento | None:
        return self._repository.get_by_hash(hash_sha256)

    def listar_documentos(self) -> list[Documento]:
        return self._repository.list()

    def recuperar_documentos_interrumpidos(self) -> list[Documento]:
        return self._recuperar_interrumpidos.execute()

    def aprobar_para_markdown(self, documento_id: str, aprobador: str, comentario: str = "") -> Documento:
        if self._aprobar_para_markdown is None:
            raise RuntimeError(
                "Modulo 12 (aprobacion para markdown) no esta configurado en este DocumentsService -- "
                "falta aprobacion_repository al construirlo."
            )
        return self._aprobar_para_markdown.execute(documento_id, aprobador, comentario)

    def listar_aprobaciones(self, documento_id: str) -> list[Aprobacion]:
        if self._aprobacion_repository is None:
            raise RuntimeError(
                "Modulo 12 (aprobacion para markdown) no esta configurado en este DocumentsService -- "
                "falta aprobacion_repository al construirlo."
            )
        return self._aprobacion_repository.list_by_document(documento_id)

    def generar_markdown(self, documento_id: str) -> Documento:
        if self._generar_markdown is None:
            raise RuntimeError(
                "Modulo 12 (generador de Markdown) no esta configurado en este DocumentsService -- "
                "falta markdown_output_store al construirlo."
            )
        return self._generar_markdown.execute(documento_id)

    def validar_markdown(self, documento_id: str) -> Documento:
        return self._validar_markdown.execute(documento_id)

    def liberar_documento(self, documento_id: str) -> Documento:
        if self._liberar_documento is None:
            raise RuntimeError(
                "Modulo 12 (liberacion) no esta configurado en este DocumentsService -- "
                "falta aprobacion_repository al construirlo."
            )
        return self._liberar_documento.execute(documento_id)

    def generar_manifiesto(self, lote_id: str | None = None) -> str:
        if self._generar_manifiesto is None:
            raise RuntimeError(
                "Modulo 12 (manifiesto) no esta configurado en este DocumentsService -- "
                "faltan vigencia_repository y/o manifest_writer al construirlo."
            )
        return self._generar_manifiesto.execute(lote_id)

    def preparar_entrega_rag_studio(self, lote_id: str | None = None) -> str:
        """Genera el manifiesto (igual que `generar_manifiesto()`) y
        ADEMAS consolida en 14_entrega_rag_studio/ una copia de ese
        manifiesto y de cada Markdown LIBERADO que referencia -- ver
        domain.documents.ports.EntregaRagStudioStore. Agregado
        2026-07-31 (comentario real del consultor)."""
        if self._preparar_entrega_rag_studio is None:
            raise RuntimeError(
                "Modulo 12 (entrega a RAG Studio) no esta configurado en este DocumentsService -- "
                "faltan vigencia_repository, manifest_writer y/o entrega_store al construirlo."
            )
        return self._preparar_entrega_rag_studio.execute(lote_id)
