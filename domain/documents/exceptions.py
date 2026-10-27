"""Excepciones del contexto Documentos."""
from __future__ import annotations


class DocumentDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class InvalidDocumentStateTransitionError(DocumentDomainError):
    def __init__(self, origen: str, destino: str):
        super().__init__(
            f"No se permite pasar el documento de '{origen}' a '{destino}' -- el flujo "
            "principal (Documento Maestro, seccion 4.7) no admite saltos ni retrocesos."
        )
        self.origen = origen
        self.destino = destino


class DuplicateDocumentHashError(DocumentDomainError):
    """El archivo que se intenta registrar ya existe en el inventario
    del proyecto (mismo hash SHA-256) -- Modulo 3: deduplicacion por
    contenido, no por nombre de archivo."""

    def __init__(self, hash_sha256: str, documento_existente_id: str):
        super().__init__(
            f"Ya existe un documento registrado con el mismo contenido (hash "
            f"{hash_sha256[:12]}...): '{documento_existente_id}'. Si es intencional, "
            "registre el archivo bajo un nombre distinto para versionarlo explicitamente."
        )
        self.hash_sha256 = hash_sha256
        self.documento_existente_id = documento_existente_id


class OriginalFileCopyError(DocumentDomainError):
    """La copia inmutable del archivo original fallo (Documento
    Maestro, seccion 4.1: "originales inmutables"). A diferencia de
    RAG STUDIO (que tolera un fallo de copia y sigue leyendo del
    origen), aqui el registro completo del documento falla -- sin
    copia local verificable no hay trazabilidad, y garantizar
    trazabilidad es el proposito de este modulo."""

    def __init__(self, ruta_origen: str, motivo: str):
        super().__init__(f"No se pudo copiar el archivo original '{ruta_origen}': {motivo}")
        self.ruta_origen = ruta_origen
        self.motivo = motivo


class SourceFileNotFoundError(DocumentDomainError):
    def __init__(self, ruta_origen: str):
        super().__init__(f"No se encontro el archivo a registrar: '{ruta_origen}'.")
        self.ruta_origen = ruta_origen


class DocumentNotFoundError(DocumentDomainError):
    def __init__(self, documento_id: str):
        super().__init__(f"No se encontro el documento '{documento_id}' en el inventario del proyecto.")
        self.documento_id = documento_id


class PdfIllegibleError(DocumentDomainError):
    """El archivo PDF no se pudo abrir/parsear en absoluto (distinto de
    "no tiene capa de texto"): un PDF corrupto o cifrado sin contrasena
    conocida no puede clasificarse automaticamente -- se enruta a
    correccion manual (Modulo 4) en vez de fallar el registro."""

    def __init__(self, ruta: str, motivo: str):
        super().__init__(f"No se pudo leer el PDF '{ruta}' para clasificarlo: {motivo}")
        self.ruta = ruta
        self.motivo = motivo


class UnsupportedFormatError(DocumentDomainError):
    """La extension del archivo no esta en la lista de formatos de
    primera version confirmada (Documento Maestro, seccion 4.4)."""

    def __init__(self, ruta_origen: str, extension: str):
        super().__init__(
            f"El archivo '{ruta_origen}' tiene una extension no admitida en la primera "
            f"version ('{extension}'). Ver Documento Maestro, seccion 4.4, para la lista "
            "de formatos confirmados."
        )
        self.ruta_origen = ruta_origen
        self.extension = extension


class UnsupportedExtractionRouteError(DocumentDomainError):
    """El Modulo 5 (extraccion directa) solo procesa documentos que el
    Modulo 4 clasifico como EXTRACCION_DIRECTA. Los enrutados a OCR
    (Modulo 6) o correccion manual todavia no tienen un modulo que los
    procese en esta version -- no es un error del documento, es un
    modulo pendiente."""

    def __init__(self, documento_id: str, tipo_procesamiento: str | None):
        super().__init__(
            f"El documento '{documento_id}' no esta clasificado como extraccion directa "
            f"(tipo_procesamiento={tipo_procesamiento!r}). Si necesita OCR, el Modulo 6 "
            "todavia no esta implementado; si necesita correccion manual, requiere "
            "intervencion humana antes de continuar."
        )
        self.documento_id = documento_id
        self.tipo_procesamiento = tipo_procesamiento


class ExtractionFailedError(DocumentDomainError):
    """El adaptador de extraccion no pudo procesar el archivo (formato
    corrupto, biblioteca subyacente incompatible, etc.)."""

    def __init__(self, ruta: str, motivo: str):
        super().__init__(f"No se pudo extraer el contenido de '{ruta}': {motivo}")
        self.ruta = ruta
        self.motivo = motivo


class OcrEngineUnavailableError(DocumentDomainError):
    """El motor OCR (Tesseract) no esta disponible: falta el binario
    en el sistema operativo, o falta el paquete de idioma solicitado
    (por ejemplo, 'tesseract-ocr-spa') -- ver ADR-001, seccion 14.1.
    pytesseract distingue ambos casos con excepciones distintas; este
    error de dominio unifica los dos en un mensaje accionable, en vez
    de dejar pasar el error crudo de un subproceso externo."""

    def __init__(self, detalle: str):
        super().__init__(detalle)


class TranscriptionEngineUnavailableError(DocumentDomainError):
    """El motor de transcripcion (Whisper local, via faster-whisper) no
    esta disponible: no se pudieron descargar/cargar los pesos del
    modelo (por ejemplo, sin acceso de red a Hugging Face Hub -- caso
    real de este entorno de desarrollo, ver README), o el archivo de
    audio/video no se pudo decodificar (ffmpeg ausente o formato no
    reconocido). Mismo principio que OcrEngineUnavailableError: un
    fallo de un motor externo real se reporta como error de dominio
    claro, nunca como un crash sin contexto."""

    def __init__(self, detalle: str):
        super().__init__(detalle)


class ReglaNormalizacionDesconocidaError(DocumentDomainError):
    """El `tipo_regla` de una `domain.profiles.entities.
    ReglaNormalizacion` no esta en el catalogo que
    `NormalizationEngine` reconoce -- Documento Maestro, seccion 4.6:
    "aplicar reglas sin alterar silenciosamente" exige que una regla mal
    configurada o de un catalogo mas nuevo que el codigo instalado
    falle de forma visible, nunca que se ignore en silencio."""

    def __init__(self, tipo_regla: str):
        super().__init__(
            f"La regla de normalizacion de tipo '{tipo_regla}' no esta reconocida por el motor -- "
            "revise el catalogo de tipos soportados en RuleBasedNormalizationEngine."
        )
        self.tipo_regla = tipo_regla


class CorreccionRequiereEstadoExtraidoError(DocumentDomainError):
    """La correccion humana del Markdown extraido (Modulo 8) solo se
    puede guardar mientras el documento sigue EXTRAIDO -- una vez
    aprobada la revision (REVISADO en adelante), el Markdown queda
    fijado para normalizacion/Markdown final; corregirlo despues
    requeriria un mecanismo de nueva version, no esta correccion."""

    def __init__(self, documento_id: str, estado_actual: str):
        super().__init__(
            f"No se puede corregir el documento '{documento_id}': esta en estado '{estado_actual}', "
            "se requiere 'extraido'. La correccion es parte de la revision contra el original "
            "(Documento Maestro, Modulo 8), antes de aprobarla."
        )
        self.documento_id = documento_id
        self.estado_actual = estado_actual


class MarkdownVacioError(DocumentDomainError):
    """El Markdown final generado (Modulo 12,
    `Documento.generar_markdown()`) esta vacio -- no se puede validar ni
    liberar un documento sin contenido util (ver
    application.documents.commands.validar_markdown.ValidarMarkdown)."""

    def __init__(self, documento_id: str):
        super().__init__(
            f"No se puede validar el documento '{documento_id}': su Markdown final esta vacio. "
            "Revise la normalizacion/correccion antes de continuar."
        )
        self.documento_id = documento_id


class LegacyConversionFailedError(DocumentDomainError):
    """La conversion previa de un documento legado (DOC/XLS, formato
    binario OLE2) a su equivalente moderno (DOCX/XLSX) via LibreOffice
    headless fallo -- binario 'soffice' ausente, archivo de entrada
    corrupto/no reconocido, o el subproceso no respondio a tiempo (ver
    ADR-001, seccion 8: 'agregar adaptadores nuevos para DOC/XLS
    legacy'). Se distingue de ExtractionFailedError porque el fallo
    ocurre antes de llegar siquiera a DocxExtractor/XlsxExtractor."""

    def __init__(self, ruta: str, motivo: str):
        super().__init__(f"No se pudo convertir el archivo legado '{ruta}' a un formato moderno: {motivo}")
        self.ruta = ruta
        self.motivo = motivo


class EntregaIntegridadError(DocumentDomainError):
    """La carpeta de entrega a RAG STUDIO (14_entrega_rag_studio/) no es
    consistente con su propio manifiesto: algun `.md` no existe o su
    SHA-256 no coincide con `hash_contenido`. RAG STUDIO rechazaria esas
    filas al importar ("el archivo fue localizado, pero su contenido no
    coincide con el hash declarado en el manifiesto") -- se detecta
    aqui, en el productor, para no entregar nunca un lote que el
    receptor va a rechazar (incidencia real 2026-09-30, lote generado en
    Windows con fines de linea CRLF). Ver
    CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md, seccion 6."""

    def __init__(self, hallazgos: list[str]):
        detalle = "\n".join(f"- {h}" for h in hallazgos)
        super().__init__(
            f"La entrega a RAG STUDIO no se preparo: {len(hallazgos)} archivo(s) no coinciden con el "
            f"hash declarado en el manifiesto.\n{detalle}\n"
            "Si el lote se genero con una version anterior en Windows, ejecute "
            "scripts/reparar_fin_de_linea_markdown.py sobre el proyecto y vuelva a preparar la entrega."
        )
        self.hallazgos = hallazgos
