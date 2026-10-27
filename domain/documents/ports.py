"""Puertos (interfaces) del contexto Documentos.

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). `DocumentRepository` opera siempre contra la base de un unico
proyecto (proyecto.db) -- a diferencia de `ProjectRepository`, que
opera contra la base global.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Optional

from domain.profiles.entities import ReglaNormalizacion

from .entities import (
    Aprobacion,
    Documento,
    EstadoDocumento,
    FilaManifiesto,
    FormatoDocumento,
    ResultadoExtraccion,
    ResultadoNormalizacion,
    ResultadoTranscripcion,
    Revision,
    TipoProcesamiento,
)
from .ocr_table_reconstruction import RangoBajaConfianza


class DocumentRepository(ABC):
    """Persistencia de documentos en la base de un proyecto
    (proyecto.db, Documento Maestro seccion 4.5)."""

    @abstractmethod
    def save(self, documento: Documento) -> None: ...

    @abstractmethod
    def get(self, documento_id: str) -> Optional[Documento]: ...

    @abstractmethod
    def get_by_hash(self, hash_sha256: str) -> Optional[Documento]:
        """Busca un documento ya registrado con el mismo contenido
        (Modulo 3: deduplicacion por hash, no por nombre de archivo)."""
        ...

    @abstractmethod
    def list_by_estado(self, estado: EstadoDocumento) -> list[Documento]:
        """Mismo proposito que TrabajoRepository.list_by_estado():
        encontrar documentos huerfanos en un estado transitorio
        (EN_EXTRACCION/EN_NORMALIZACION) tras un fallo sin manejar de
        una version anterior o un cierre no controlado de la aplicacion
        -- ver application.documents.commands.
        recuperar_documentos_interrumpidos.RecuperarDocumentosInterrumpidos
        (bug real encontrado 2026-07-29, usuario sin Tesseract
        instalado)."""
        ...

    @abstractmethod
    def list(self) -> list[Documento]: ...


class RevisionRepository(ABC):
    """Persistencia del historial de revisiones (Modulo 8, ADR-001
    seccion 5) en la base de un proyecto (proyecto.db). A diferencia de
    `DocumentRepository.save()` (que actualiza el mismo registro), cada
    `Revision` es un registro nuevo e inmutable -- no hay `update`."""

    @abstractmethod
    def save(self, revision: Revision) -> None: ...

    @abstractmethod
    def list_by_document(self, documento_id: str) -> list[Revision]: ...


class AprobacionRepository(ABC):
    """Persistencia del historial de aprobaciones para generar Markdown
    (Modulo 12/13, ADR-001 seccion 5) en la base de un proyecto
    (proyecto.db). Mismo principio que `RevisionRepository`: cada
    `Aprobacion` es un registro nuevo e inmutable -- no hay `update`."""

    @abstractmethod
    def save(self, aprobacion: Aprobacion) -> None: ...

    @abstractmethod
    def list_by_document(self, documento_id: str) -> list[Aprobacion]: ...


class ManifestWriter(ABC):
    """Escribe el manifiesto de entrega hacia RAG STUDIO (Modulo 12,
    Documento Maestro seccion 4.6.1) a disco -- no sabe nada de
    Documento/Fuente/Vigencia, solo de `FilaManifiesto` ya armadas por
    `application.documents.commands.generar_manifiesto.
    GenerarManifiesto`."""

    @abstractmethod
    def escribir(self, filas: list[FilaManifiesto]) -> str:
        """Escribe `filas` (puede ser una lista vacia -- proyecto sin
        documentos LIBERADO todavia) y devuelve la ruta absoluta del
        archivo escrito. Determinista: mismo nombre de archivo cada vez
        (Documento Maestro, seccion 4.11.1: "el comportamiento es
        determinista"), sobrescribiendo la version anterior -- el
        manifiesto siempre refleja el estado LIBERADO actual del
        proyecto completo, no un historial acumulado."""
        ...


class EntregaRagStudioStore(ABC):
    """Consolida en UNA sola carpeta (14_entrega_rag_studio/, Documento
    Maestro seccion 4.5) los archivos que se deben entregar a RAG STUDIO
    (seccion 4.6.1): una copia del manifiesto y de cada Markdown LIBERADO
    que referencia -- para que el operador no tenga que ir a buscarlos
    por separado a 07_markdown/ y 12_exportaciones/ (comentario real del
    consultor, 2026-07-31). No sustituye el manifiesto canonico de
    12_exportaciones/ (`ManifestWriter`) ni cambia su contenido/formato
    -- es una copia adicional, puramente de conveniencia, pensada para
    poder copiar/entregar una sola carpeta."""

    @abstractmethod
    def preparar(
        self, ruta_manifiesto: str, rutas_markdown: list[str], identificador_entrega: str | None = None
    ) -> str:
        """Dos modos, segun `identificador_entrega` (agregado 2026-10-03
        a pedido de NEXOM, Solicitud_Ajustes_RAG_Content_Lotes_y_
        Portabilidad.pdf, seccion 3: "cada lote debe exportarse en una
        carpeta independiente... no sobrescribir, mezclar ni eliminar
        archivos... de entregas anteriores"):

        - `None` (comportamiento ORIGINAL, sin cambios): recrea la
          carpeta de entrega raiz DESDE CERO (se borra cualquier
          contenido de una corrida anterior antes de copiar) -- mismo
          criterio determinista que `ManifestWriter.escribir()`. Pensado
          para la entrega de TODO el proyecto (`lote_id=None` en
          `PrepararEntregaRagStudio`), que sigue siendo una unica
          carpeta fija que siempre refleja el conjunto LIBERADO actual
          completo.
        - Un identificador concreto (tipicamente `"<id_lote>_<nombre
          legible del lote>"`): crea una SUBCARPETA de version nueva
          (`v1`, `v2`, ...) dentro de `<identificador_entrega>/`, sin
          tocar ninguna version anterior de ESE lote ni la entrega (o
          las entregas de otros lotes) que ya existan junto a ella. Cada
          lote cerrado por separado queda en su propia subcarpeta,
          nunca se mezclan ni se sobrescriben entre si.

        En ambos modos: copia `ruta_manifiesto` y cada ruta de
        `rutas_markdown` (puede ser una lista vacia) con su mismo nombre
        de archivo, verifica la integridad de lo copiado, y devuelve la
        ruta absoluta de la carpeta final (la raiz en el primer modo, la
        subcarpeta de version nueva en el segundo)."""
        ...


class OriginalFileStore(ABC):
    """Copia inmutable del archivo original dentro de
    01_originales/ del proyecto, calculando su hash SHA-256 en el
    mismo paso (para no leer el archivo dos veces)."""

    @abstractmethod
    def copiar_original(self, ruta_origen: str) -> tuple[str, str, int]:
        """Copia `ruta_origen` a la carpeta de originales del proyecto
        y devuelve (ruta_copia, hash_sha256, tamano_bytes).

        Debe fallar (ver domain.documents.exceptions.
        OriginalFileCopyError / SourceFileNotFoundError) en vez de
        devolver un resultado parcial -- decision deliberada distinta
        a RAG STUDIO, que tolera que la copia falle y sigue leyendo del
        origen (ver Documento.ruta_copia_original)."""
        ...


class PdfTextLayerDetector(ABC):
    """Decide si un PDF tiene capa de texto real o es una imagen
    escaneada -- la pregunta que el Modulo 4 (Clasificacion y
    enrutamiento) necesita responder para elegir entre extraccion
    directa y OCR. Mismo criterio que RAG STUDIO usa pagina por pagina
    en su PdfTextExtractor (page.extract_text() con pypdf), pero aqui a
    nivel de documento completo: basta que una sola pagina tenga texto
    para no enrutar todo el documento a OCR (Modulo 5 decidira, pagina
    por pagina, igual que RAG STUDIO, si aplica OCR a las paginas
    faltantes)."""

    @abstractmethod
    def tiene_capa_de_texto(self, ruta: str) -> bool:
        """True si al menos una pagina produce texto extraible.

        Debe lanzar domain.documents.exceptions.PdfIllegibleError si el
        archivo no se puede abrir o parsear en absoluto (PDF corrupto o
        cifrado) -- en ese caso el documento se enruta a correccion
        manual en vez de fallar la clasificacion completa."""
        ...


class DocumentExtractor(ABC):
    """Extrae el contenido de un documento y lo normaliza a Markdown
    real (Modulo 5 -- extraccion directa; Modulo 6 -- OCR). Solo se
    invoca sobre documentos que el Modulo 4 clasifico como
    EXTRACCION_DIRECTA u OCR -- ver
    domain.documents.exceptions.UnsupportedExtractionRouteError.

    `tipo_procesamiento` se incluye en la firma (y no solo `formato`)
    porque un mismo formato puede necesitar dos adaptadores distintos
    segun la ruta que decidio el Modulo 4 -- un PDF EXTRACCION_DIRECTA
    usa capa de texto real; un PDF OCR (sin capa de texto) necesita
    rasterizarse y reconocerse pagina por pagina. Los formatos sin esa
    ambiguedad (DOCX, XLSX, CSV, TXT, Markdown, JSON: siempre
    EXTRACCION_DIRECTA; PNG/JPG: siempre OCR) simplemente ignoran el
    parametro en su `supports()`.

    `on_progreso` (agregado 2026-07-31, comentario real del consultor:
    captura de pantalla de un dialogo de progreso de Windows en negro,
    con botones "Forzar la salida"/"Esperar" -- el aviso nativo de
    Windows de que la aplicacion dejo de responder) es un callback
    opcional `(pagina_actual, total_paginas) -> None` que un extractor
    puede invocar durante su trabajo para que quien llama (la interfaz)
    pueda hacer `QApplication.processEvents()` con mas frecuencia que
    "una vez por documento". Sigue sin haber ningun hilo real de por
    medio (ver ui.wizard.etapas.EtapaProcesar): el problema no era que
    faltara un QProgressDialog (ya se habia agregado, ver el fix
    anterior ese mismo dia) sino que, con un solo documento pendiente o
    un documento con muchas paginas, `processEvents()` solo se llamaba
    UNA vez antes de bloquear el hilo de la interfaz durante todo el
    OCR de ese documento -- tiempo mas que suficiente para que Windows
    considere la ventana "no responde". Solo `PdfOcrExtractor` (Modulo
    6, el unico tramo genuinamente lento pagina por pagina en este
    contexto) lo invoca de verdad; los demas extractores lo reciben y
    lo ignoran sin romper su contrato."""

    @abstractmethod
    def supports(self, formato: FormatoDocumento, tipo_procesamiento: TipoProcesamiento) -> bool: ...

    @abstractmethod
    def extract(
        self,
        ruta: str,
        formato: FormatoDocumento,
        tipo_procesamiento: TipoProcesamiento,
        on_progreso: Callable[[int, int], None] | None = None,
    ) -> ResultadoExtraccion:
        """Debe lanzar domain.documents.exceptions.ExtractionFailedError
        si el archivo no se puede procesar en absoluto -- una pagina o
        hoja vacia se reporta como advertencia dentro de
        ResultadoExtraccion.advertencias, nunca como excepcion."""
        ...


class ExtractionOutputStore(ABC):
    """Persiste el Markdown resultante dentro de 03_extracciones/ del
    proyecto (Documento Maestro, seccion 4.5)."""

    @abstractmethod
    def guardar(self, documento_id: str, markdown: str) -> str:
        """Devuelve la ruta absoluta del archivo escrito."""
        ...


class LegacyFormatConverter(ABC):
    """Convierte un documento legado (DOC/XLS, formato binario OLE2) a
    su equivalente moderno (DOCX/XLSX respectivamente) usando
    LibreOffice en modo headless -- unico motor de conversion viable
    sin depender de Microsoft Office (ADR-001, seccion 8: 'agregar
    adaptadores nuevos para DOC/XLS legacy, conversion previa con
    LibreOffice headless'). Quien usa este puerto es
    infrastructure.extraction.doc_legacy_extractor/xls_legacy_extractor,
    que delegan la extraccion real en DocxExtractor/XlsxExtractor
    (Modulo 5) sobre el archivo ya convertido -- este puerto no sabe
    nada de Markdown, solo de formatos de archivo."""

    @abstractmethod
    def convertir(self, ruta: str, formato_destino: FormatoDocumento) -> str:
        """Convierte `ruta` (DOC o XLS) al formato moderno indicado por
        `formato_destino` (DOCX o XLSX) y devuelve la ruta absoluta del
        archivo resultante, dentro de un directorio temporal exclusivo
        de esta conversion -- quien llama es responsable de borrar ese
        directorio una vez que termino de leer el archivo convertido
        (ver los extractores legado, que lo hacen en un try/finally
        inmediatamente despues de extraer).

        Debe lanzar domain.documents.exceptions.LegacyConversionFailedError
        si LibreOffice no esta instalado, si el archivo de entrada esta
        corrupto o no se reconoce, o si el subproceso no responde a
        tiempo."""
        ...


class TranscriptionEngine(ABC):
    """Adaptador hacia un motor de transcripcion real (Whisper local,
    via faster-whisper -- ADR-001, seccion 14.1, confirmado 2026-07-28
    al entrar audio/video a la primera version). Solo sabe convertir un
    archivo de audio/video ya decodificable en una lista de `Segmento`;
    quien decide cuando hace falta y arma el Markdown final es
    infrastructure.extraction.audio_video_transcription_extractor
    (mismo reparto de responsabilidades que OcrEngine/
    image_ocr_extractor, Modulo 6)."""

    @abstractmethod
    def transcribir(self, ruta: str) -> ResultadoTranscripcion:
        """Transcribe el archivo de audio/video en `ruta` a una lista
        ordenada de `Segmento` (ver su docstring).

        Debe lanzar domain.documents.exceptions.
        TranscriptionEngineUnavailableError si el modelo no se pudo
        cargar (pesos no descargables/instalados) o si el archivo no se
        pudo decodificar (ffmpeg ausente o formato no reconocido)."""
        ...


class NormalizationEngine(ABC):
    """Motor de reglas propio del Modulo 9 (Documento Maestro, seccion
    4.6: "aplicar reglas sin alterar silenciosamente"). Las reglas
    (`domain.profiles.entities.ReglaNormalizacion`) las define el
    perfil del proyecto -- "reglas en YAML por perfil" (ADR-001, seccion
    8) -- pero quien las ejecuta sobre el Markdown de un documento es
    este puerto, invocado por
    application.documents.commands.normalizar_documento.NormalizarDocumento
    solo sobre documentos ya REVISADO (Modulo 8)."""

    @abstractmethod
    def normalizar(self, markdown: str, reglas: list[ReglaNormalizacion]) -> ResultadoNormalizacion:
        """Aplica `reglas`, en orden, sobre `markdown` y devuelve el
        resultado junto con un registro transparente de cada cambio
        real (ver ResultadoNormalizacion.cambios) -- una regla sin
        efecto sobre este documento no es un error, simplemente no
        agrega nada al registro.

        Debe lanzar domain.documents.exceptions.
        ReglaNormalizacionDesconocidaError si `tipo_regla` de alguna
        regla no esta en el catalogo reconocido -- nunca debe ignorar
        una regla que no entiende."""
        ...


class OcrEngine(ABC):
    """Adaptador hacia un motor OCR real (Tesseract, via pytesseract --
    ADR-001, seccion 14.1, confirmado 2026-07-28). Solo sabe convertir
    una imagen ya rasterizada de una sola pagina en texto; quien decide
    cuando hace falta y arma el resultado final es
    infrastructure.extraction.image_ocr_extractor/pdf_ocr_extractor
    (mismo reparto de responsabilidades que RAG STUDIO)."""

    @abstractmethod
    def image_to_text(self, image_bytes: bytes) -> tuple[str, list[str], list[RangoBajaConfianza]]:
        """image_bytes: una imagen ya rasterizada (PNG) de una sola
        pagina. Devuelve `(texto, advertencias, rangos_baja_confianza)`:
        `texto` es el reconocido (puede ser cadena vacia si la pagina no
        tiene texto legible); `advertencias` (agregado 2026-07-31,
        PROY-6955_udl_3) senala problemas detectados durante la
        reconstruccion (por ejemplo, una posible fila de tabla
        incompleta -- ver
        domain.documents.ocr_table_reconstruction.reconstruir_texto_ocr())
        sin alterar `texto` -- vacia si no hay nada que senalar.
        `rangos_baja_confianza` (agregado 2026-08-01, a pedido del
        consultor: dirigir la atencion del revisor de "Revision", Modulo
        8, hacia lo que el propio OCR reconoce como incierto) ubica los
        tramos de `texto` que corresponden a palabras reconocidas con
        confianza por debajo de
        domain.documents.ocr_table_reconstruction.UMBRAL_CONFIANZA_BAJA
        -- vacia si ninguna palabra cayo por debajo del umbral.

        Debe lanzar domain.documents.exceptions.OcrEngineUnavailableError
        si el binario de Tesseract o el paquete de idioma configurado
        no estan instalados en el sistema operativo."""
        ...
