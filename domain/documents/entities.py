"""Entidades y catalogos del contexto Documentos (Documento Maestro,
secciones 4.4, 4.6 y 4.7). Incluye la entidad `Documento` (Modulo 3:
inventario documental con hash SHA-256), inspirada en `Source` de RAG
STUDIO (domain/documents/entities.py) pero mas simple: RAG Content
Studio Desktop todavia no gobierna vigencia/autoridad entre fuentes --
eso es propio de RAG STUDIO, no de esta herramienta (ADR-001, seccion
4.6.1: RAG Content Studio Desktop entrega Markdown, no decide que fuente
prevalece). Lo que si comparte con Source es el principio de "copia
local inmutable + hash de integridad" para poder demostrar trazabilidad
completa (Documento Maestro, seccion 4.1).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .exceptions import CorreccionRequiereEstadoExtraidoError, InvalidDocumentStateTransitionError
from .ocr_table_reconstruction import RangoBajaConfianza

_HASH_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FormatoDocumento(str, Enum):
    """Formatos de entrada confirmados para la primera version
    (Documento Maestro, seccion 4.4, ampliada 2026-07-28; audio/video
    confirmados 2026-07-28, salen de "extension posterior")."""

    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    TXT = "txt"
    MARKDOWN = "markdown"
    JSON = "json"
    PNG = "png"
    JPG = "jpg"
    MP3 = "mp3"
    WAV = "wav"
    M4A = "m4a"
    MP4 = "mp4"
    MOV = "mov"


class EstadoDocumento(str, Enum):
    """Flujo principal + estados alternos (Documento Maestro, seccion
    4.7). No debe saltarse ningun estado del flujo principal; la
    maquina de estados que lo impone vive en application, no aqui --
    este enum solo declara el vocabulario."""

    RECIBIDO = "recibido"
    INVENTARIADO = "inventariado"
    CLASIFICADO = "clasificado"
    EN_EXTRACCION = "en_extraccion"
    EXTRAIDO = "extraido"
    EN_REVISION = "en_revision"
    REVISADO = "revisado"
    EN_NORMALIZACION = "en_normalizacion"
    NORMALIZADO = "normalizado"
    PENDIENTE_DE_APROBACION = "pendiente_de_aprobacion"
    APROBADO_PARA_MARKDOWN = "aprobado_para_markdown"
    MARKDOWN_GENERADO = "markdown_generado"
    VALIDADO = "validado"
    LIBERADO = "liberado"
    # Estados alternos:
    OBSERVADO = "observado"
    BLOQUEADO = "bloqueado"
    DESCARTADO = "descartado"
    OBSOLETO = "obsoleto"


FLUJO_PRINCIPAL: list[EstadoDocumento] = [
    EstadoDocumento.RECIBIDO,
    EstadoDocumento.INVENTARIADO,
    EstadoDocumento.CLASIFICADO,
    EstadoDocumento.EN_EXTRACCION,
    EstadoDocumento.EXTRAIDO,
    EstadoDocumento.EN_REVISION,
    EstadoDocumento.REVISADO,
    EstadoDocumento.EN_NORMALIZACION,
    EstadoDocumento.NORMALIZADO,
    EstadoDocumento.PENDIENTE_DE_APROBACION,
    EstadoDocumento.APROBADO_PARA_MARKDOWN,
    EstadoDocumento.MARKDOWN_GENERADO,
    EstadoDocumento.VALIDADO,
    EstadoDocumento.LIBERADO,
]
"""Orden exacto del flujo principal (Documento Maestro, seccion 4.7).
`EstadoDocumento` en si no impide saltos -- es solo vocabulario; la
regla de transicion vive en `Documento.avanzar_a()` (ver mas abajo)."""

_INDICE_FLUJO: dict[EstadoDocumento, int] = {estado: i for i, estado in enumerate(FLUJO_PRINCIPAL)}
_ESTADOS_ALTERNOS_DESDE_FLUJO = frozenset(
    {EstadoDocumento.OBSERVADO, EstadoDocumento.BLOQUEADO, EstadoDocumento.DESCARTADO}
)


def _transiciones_permitidas(origen: EstadoDocumento) -> frozenset[EstadoDocumento]:
    """Reglas conservadoras para Modulo 3 (inventario): solo garantiza
    que nunca se salte un paso del flujo principal y que los estados
    alternos (observado/bloqueado/descartado/obsoleto) se usen como
    valvula de escape razonable. Los modulos de revision y normalizacion
    (Modulo 6 en adelante) son los duenos reales de las reglas finas
    de esos estados alternos y pueden refinar esta tabla sin tocar el
    resto del nucleo -- este modulo solo necesita que RECIBIDO ->
    INVENTARIADO sea real y verificable."""
    if origen == EstadoDocumento.LIBERADO:
        return frozenset({EstadoDocumento.OBSOLETO})
    if origen in (EstadoDocumento.DESCARTADO, EstadoDocumento.OBSOLETO):
        return frozenset()
    if origen in (EstadoDocumento.OBSERVADO, EstadoDocumento.BLOQUEADO):
        # Auditoria 2026-08-24: BLOQUEADO faltaba en este conjunto, asi que
        # OBSERVADO -> BLOQUEADO (la resolucion que aplica
        # application.batches.commands.cerrar_lote.CerrarLote a cualquier
        # documento sin resolver, incluido uno en OBSERVADO) lanzaba
        # InvalidDocumentStateTransitionError sin capturar y abortaba el
        # cierre de lote a mitad de camino. No es explotable hoy (ningun
        # caso de uso ni la UI ponen un documento en OBSERVADO todavia),
        # pero es un defecto real del contrato entre el dominio y
        # CerrarLote -- un estado alterno debe poder moverse a otro estado
        # alterno mas restrictivo sin excepcion.
        return frozenset(FLUJO_PRINCIPAL) - {EstadoDocumento.LIBERADO} | {
            EstadoDocumento.DESCARTADO,
            EstadoDocumento.BLOQUEADO,
        }
    siguiente_indice = _INDICE_FLUJO[origen] + 1
    permitidos = set(_ESTADOS_ALTERNOS_DESDE_FLUJO)
    if siguiente_indice < len(FLUJO_PRINCIPAL):
        permitidos.add(FLUJO_PRINCIPAL[siguiente_indice])
    return frozenset(permitidos)


class Prioridad(str, Enum):
    """Prioridad de procesamiento del documento dentro de la cola de
    trabajos (ADR-001, seccion 10: "control de prioridad")."""

    BAJA = "baja"
    NORMAL = "normal"
    ALTA = "alta"
    URGENTE = "urgente"


class Criticidad(str, Enum):
    """Si el documento pertenece a un tipo documental critico segun el
    perfil del proyecto (`PerfilProyecto.tipos_documentales_criticos`)
    -- afecta cuantas incidencias se toleran antes de bloquear su
    liberacion (Documento Maestro, seccion 4.3: "incidencias criticas
    permitidas")."""

    NO_CRITICO = "no_critico"
    CRITICO = "critico"


class TipoProcesamiento(str, Enum):
    """Ruta de procesamiento asignada por el Modulo 4 (Clasificacion y
    enrutamiento, Documento Maestro seccion 4.6). TRANSCRIPCION
    (Modulo 7) agregada 2026-07-28 al confirmarse audio/video como
    formatos de entrada de la primera version (antes en "extension
    posterior", seccion 4.4)."""

    EXTRACCION_DIRECTA = "extraccion_directa"
    OCR = "ocr"
    TRANSCRIPCION = "transcripcion"
    CORRECCION_MANUAL = "correccion_manual"


class Documento(BaseModel):
    """Entidad raiz del inventario documental (Modulo 3). Cada
    Documento vive en la base de un unico proyecto (proyecto.db) --
    nunca en la base global -- y su copia local original es inmutable
    una vez registrada (Documento Maestro, seccion 4.1: "originales
    inmutables"; ver domain.documents.ports.OriginalFileStore)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proyecto_id: str
    nombre_original: str
    formato: FormatoDocumento
    ruta_origen: str
    """Ruta donde vivia el archivo antes de registrarlo (puede quedar
    fuera de la ruta raiz confirmada -- es de donde lo trajo el
    usuario). Nunca se usa para leer despues del registro; para eso
    esta `ruta_copia_original`."""
    ruta_copia_original: str
    """Ruta de la copia inmutable dentro de 01_originales/ del
    proyecto (Documento Maestro, seccion 4.5). A diferencia de
    `Source.original_copy_path` en RAG STUDIO (que acepta `None` si la
    copia falla -- fallo silencioso), aqui es obligatorio: si la copia
    falla, el registro completo falla (ver
    LocalOriginalFileStore/RegistrarDocumento) porque sin copia local
    no hay trazabilidad verificable, y ese es justamente el requisito
    que este modulo existe para cumplir."""
    hash_sha256: str
    tamano_bytes: int
    estado: EstadoDocumento = EstadoDocumento.RECIBIDO
    prioridad: Prioridad = Prioridad.NORMAL
    criticidad: Criticidad = Criticidad.NO_CRITICO
    metadatos: dict[str, str] = Field(default_factory=dict)
    """Valores capturados para los `CampoMetadato` del perfil del
    proyecto (domain.profiles.entities.CampoMetadato) -- este modulo no
    valida esos valores contra el perfil todavia (eso corresponde al
    Modulo de clasificacion/revision); solo los guarda."""
    tipo_procesamiento: Optional[TipoProcesamiento] = None
    """Asignado por el Modulo 4 al clasificar el documento (ver
    `Documento.clasificar()`); `None` hasta entonces."""
    ruta_extraccion: Optional[str] = None
    """Ruta del Markdown producido por el Modulo 5 dentro de
    03_extracciones/ del proyecto (ver `Documento.completar_extraccion()`);
    `None` hasta entonces."""
    advertencias_extraccion: list[str] = Field(default_factory=list)
    """Avisos no bloqueantes de la extraccion (por ejemplo, una pagina
    de PDF sin texto) -- no impiden llegar a EXTRAIDO, pero quedan
    visibles para la revision del Modulo 8."""
    mapa_paginas: list[int] = Field(default_factory=list)
    """Modulo 8 (navegacion sincronizada real): `mapa_paginas[i]` es el
    desplazamiento en caracteres, dentro del Markdown de
    `ruta_extraccion`, donde comienza el contenido de la pagina `i` del
    original (0-indexado). Solo lo llenan los extractores que procesan
    PDF pagina por pagina (PdfExtractor, PdfOcrExtractor via
    ResultadoExtraccion.mapa_paginas); el resto de formatos lo deja
    vacio -- sin mapa no hay como sincronizar, y la GUI simplemente no
    desplaza el panel de Markdown en ese caso, sin fallar."""
    rangos_baja_confianza: list[RangoBajaConfianza] = Field(default_factory=list)
    """Modulo 8 (agregado 2026-08-01, a pedido del consultor: dirigir la
    atencion del revisor hacia lo que el propio OCR reconoce como
    incierto, en vez de exigirle releer todo el documento). Tramos del
    Markdown de `ruta_extraccion` que corresponden a palabras que
    Tesseract reconocio con baja confianza -- mismo sistema de
    coordenadas que `mapa_paginas`. Solo lo llenan los extractores OCR
    (PdfOcrExtractor/ImageOcrExtractor vía
    ResultadoExtraccion.rangos_baja_confianza); la extraccion directa
    (sin OCR de por medio) lo deja vacio -- no hay ninguna confianza que
    reportar sobre texto que nunca se reconocio con OCR. Mismo
    limite ya aceptado que `mapa_paginas`: `corregir()` no los
    recalcula, asi que tras una correccion manual pueden quedar
    apuntando a un desplazamiento que ya no corresponde al mismo
    contenido -- la interfaz debe tratarlos como una guia aproximada,
    nunca como una verdad absoluta sobre el texto ya editado."""
    ruta_revisado: Optional[str] = None
    """Modulo 8 (correccion): ruta del Markdown corregido a mano por el
    revisor, dentro de 05_revisiones/ del proyecto (ver
    `Documento.corregir()`). `None` hasta la primera correccion
    guardada -- puede guardarse varias veces mientras el documento
    sigue EXTRAIDO, sin avanzar de estado. Tiene prioridad sobre
    `ruta_extraccion` para todo lo que ocurre despues (mostrar en la
    GUI, normalizar) -- ver Documento.markdown_vigente()."""
    ruta_normalizado: Optional[str] = None
    """Ruta del Markdown normalizado producido por el Modulo 9 dentro
    de 06_normalizados/ del proyecto (ver
    `Documento.completar_normalizacion()`); `None` hasta entonces."""
    cambios_normalizacion: list[str] = Field(default_factory=list)
    """Registro transparente de cada cambio aplicado por el Modulo 9
    (que regla, que efecto tuvo) -- Documento Maestro, seccion 4.6:
    "aplicar reglas sin alterar silenciosamente". Vacio no significa
    que no se ejecutaron reglas: significa que ninguna tuvo efecto
    sobre este documento en particular."""
    ruta_markdown: Optional[str] = None
    """Modulo 12 (Generador de Markdown): ruta del archivo final de
    entrega dentro de 07_markdown/ del proyecto -- ver
    Documento.generar_markdown(). `None` hasta que el documento llega a
    MARKDOWN_GENERADO. A diferencia de ruta_extraccion/ruta_normalizado
    (borradores intermedios de trabajo interno), este es el archivo que
    efectivamente se entrega a RAG STUDIO (Documento Maestro, seccion
    4.6.1) -- una copia deliberada del Markdown vigente en el momento de
    la aprobacion, nunca una referencia a 06_normalizados/, para que una
    correccion posterior sobre un documento ya normalizado (si algun dia
    se permite) no altere en silencio un archivo ya entregado."""
    hash_markdown: Optional[str] = None
    """SHA-256 del contenido de `ruta_markdown` en el momento en que se
    genero -- distinto de `hash_sha256` (que es del archivo ORIGINAL,
    Modulo 3). Es el hash que efectivamente corresponde al contenido
    entregado a RAG STUDIO (columna hash_contenido del manifiesto,
    seccion 4.6.1) -- usar hash_sha256 ahi describiria un archivo
    distinto del que realmente se entrega."""
    advertencias_markdown: list[str] = Field(default_factory=list)
    """Modulo 12 (validacion tecnica, Documento.validar_markdown()):
    avisos no bloqueantes sobre el Markdown final -- por ejemplo, que no
    contiene ningun encabezado ni tabla Markdown real, lo que impide que
    RAG STUDIO lo fragmente por encabezado o por tabla (seccion 4.6.1) y
    lo tratara como un solo bloque. Igual que advertencias_extraccion,
    nunca bloquea VALIDADO por si sola -- es informacion para el
    operador antes de liberar."""
    lote_id: Optional[str] = None
    """Fase 7 (Lotes): a que `domain.batches.entities.Lote` pertenece
    este documento, si a alguno -- `None` si todavia no se agrego a
    ningun lote (Documento Maestro, seccion 4.10: "un Proyecto contiene
    Lotes y Documentos"). Referencia por id plano, sin tipo ni
    validacion aqui -- domain.documents no importa domain.batches en
    absoluto, mismo aislamiento estricto que el resto de contextos;
    quien valida que el lote referenciado exista y siga ABIERTO es
    `application.batches.commands.agregar_documento_a_lote.
    AgregarDocumentoALote`. Un documento pertenece, como maximo, a un
    solo lote a la vez -- asignarlo a uno nuevo reemplaza la asignacion
    anterior, no la acumula."""
    version: int = 1
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("nombre_original")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre original del documento no puede estar vacio")
        return v

    @field_validator("hash_sha256")
    @classmethod
    def _hash_formato_valido(cls, v: str) -> str:
        v = v.lower().strip()
        if not _HASH_SHA256_PATTERN.match(v):
            raise ValueError(f"hash_sha256 debe ser un hash SHA-256 hexadecimal de 64 caracteres, recibido: {v!r}")
        return v

    @field_validator("tamano_bytes")
    @classmethod
    def _tamano_no_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("tamano_bytes no puede ser negativo")
        return v

    def avanzar_a(self, target: EstadoDocumento) -> "Documento":
        target = EstadoDocumento(target)
        permitidos = _transiciones_permitidas(self.estado)
        if target not in permitidos:
            raise InvalidDocumentStateTransitionError(self.estado.value, target.value)
        data = self.model_dump()
        data["estado"] = target
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def clasificar(self, tipo_procesamiento: TipoProcesamiento) -> "Documento":
        """Modulo 4 (Clasificacion y enrutamiento): fija la ruta de
        procesamiento y avanza INVENTARIADO -> CLASIFICADO en un solo
        paso atomico -- quien llama nunca puede fijar tipo_procesamiento
        sin tambien transicionar el estado (evita un Documento
        "clasificado" a medias, con el campo puesto pero el estado
        todavia en INVENTARIADO)."""
        documento = self.avanzar_a(EstadoDocumento.CLASIFICADO)
        data = documento.model_dump()
        data["tipo_procesamiento"] = TipoProcesamiento(tipo_procesamiento)
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def completar_extraccion(
        self,
        ruta_extraccion: str,
        advertencias: list[str] | None = None,
        mapa_paginas: list[int] | None = None,
        rangos_baja_confianza: list[RangoBajaConfianza] | None = None,
    ) -> "Documento":
        """Modulo 5 (Extraccion documental): fija la ruta del Markdown
        extraido y avanza EN_EXTRACCION -> EXTRAIDO en un solo paso
        atomico -- mismo principio que `clasificar()`. Quien llama debe
        haber pasado antes por `avanzar_a(EstadoDocumento.EN_EXTRACCION)`
        (CLASIFICADO -> EN_EXTRACCION es un paso aparte, para que un
        futuro worker en segundo plano pueda persistir ese estado
        intermedio sin tocar este metodo)."""
        documento = self.avanzar_a(EstadoDocumento.EXTRAIDO)
        data = documento.model_dump()
        data["ruta_extraccion"] = ruta_extraccion
        data["advertencias_extraccion"] = advertencias or []
        data["mapa_paginas"] = mapa_paginas or []
        data["rangos_baja_confianza"] = rangos_baja_confianza or []
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def marcar_extraccion_fallida(self) -> "Documento":
        """Revierte EN_EXTRACCION -> CLASIFICADO cuando el motor de
        extraccion real (OCR/transcripcion/extraccion directa) lanza una
        excepcion -- bug real encontrado 2026-07-29: sin este metodo,
        `ExtraerDocumento.execute()` guardaba EN_EXTRACCION antes de
        invocar al extractor y, si este fallaba (ej. Tesseract no
        instalado), el documento quedaba atascado ahi para siempre --
        `avanzar_a()` es de un solo sentido y EN_EXTRACCION -> EN_EXTRACCION
        no es una transicion valida, asi que ni siquiera el reintento
        (ya con la dependencia instalada) podia recuperarlo. No usa
        `avanzar_a()` (que solo permite avanzar) porque esto no es un
        paso de negocio del flujo principal, es la reversion de un
        intento fallido -- analogo a nunca haber llegado a
        EN_EXTRACCION. Solo valido si el estado actual es EN_EXTRACCION."""
        if self.estado != EstadoDocumento.EN_EXTRACCION:
            raise InvalidDocumentStateTransitionError(self.estado.value, EstadoDocumento.CLASIFICADO.value)
        data = self.model_dump()
        data["estado"] = EstadoDocumento.CLASIFICADO
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def corregir(self, ruta_revisado: str) -> "Documento":
        """Modulo 8 (correccion contra el original): guarda una nueva
        version corregida a mano del Markdown extraido, SIN avanzar de
        estado -- a diferencia de completar_extraccion()/
        completar_normalizacion(), puede llamarse varias veces mientras
        el documento sigue EXTRAIDO, cada vez que el revisor guarda un
        cambio en el panel de edicion (ver
        application.documents.commands.corregir_extraccion)."""
        if self.estado != EstadoDocumento.EXTRAIDO:
            raise CorreccionRequiereEstadoExtraidoError(self.id, self.estado.value)
        data = self.model_dump()
        data["ruta_revisado"] = ruta_revisado
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def ruta_markdown_vigente(self) -> Optional[str]:
        """Cual archivo de Markdown refleja mejor el contenido actual
        del documento, en orden de prioridad: normalizado (Modulo 9) ->
        corregido (Modulo 8, `ruta_revisado`) -> extraido en crudo
        (Modulo 5). Usado tanto por la GUI (que panel mostrar) como por
        NormalizarDocumento (que Markdown normalizar) -- un mismo
        criterio, nunca duplicado."""
        return self.ruta_normalizado or self.ruta_revisado or self.ruta_extraccion

    def completar_normalizacion(self, ruta_normalizado: str, cambios: list[str] | None = None) -> "Documento":
        """Modulo 9 (Normalizacion): fija la ruta del Markdown
        normalizado y avanza EN_NORMALIZACION -> NORMALIZADO en un solo
        paso atomico -- mismo principio que `completar_extraccion()`.
        Quien llama debe haber pasado antes por
        `avanzar_a(EstadoDocumento.EN_NORMALIZACION)`, que a su vez solo
        es alcanzable desde REVISADO (Modulo 8) -- el flujo principal no
        permite normalizar un documento que todavia no paso por
        revision humana."""
        documento = self.avanzar_a(EstadoDocumento.NORMALIZADO)
        data = documento.model_dump()
        data["ruta_normalizado"] = ruta_normalizado
        data["cambios_normalizacion"] = cambios or []
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def marcar_normalizacion_fallida(self) -> "Documento":
        """Revierte EN_NORMALIZACION -> REVISADO cuando el motor de
        normalizacion (reglas del perfil) lanza una excepcion -- mismo
        bug y mismo criterio que `marcar_extraccion_fallida()` (ver su
        docstring). Solo valido si el estado actual es EN_NORMALIZACION."""
        if self.estado != EstadoDocumento.EN_NORMALIZACION:
            raise InvalidDocumentStateTransitionError(self.estado.value, EstadoDocumento.REVISADO.value)
        data = self.model_dump()
        data["estado"] = EstadoDocumento.REVISADO
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def aprobar_para_markdown(self) -> "Documento":
        """Modulo 13 (Estados y dependencias) + Modulo 12 (Generador de
        Markdown): avanza NORMALIZADO -> PENDIENTE_DE_APROBACION ->
        APROBADO_PARA_MARKDOWN en un solo paso atomico -- mismo
        principio que `RevisarDocumento` colapsando EXTRAIDO ->
        EN_REVISION -> REVISADO. PENDIENTE_DE_APROBACION es aqui un
        estado de transito, no uno que se quede persistido a medias: no
        existe today un caso de uso que dependa de un documento
        "pendiente" durante un tiempo prolongado (a diferencia de
        EN_EXTRACCION, pensado para que un worker en segundo plano lo
        deje asi mientras trabaja -- ver completar_extraccion()).

        Quien llama (application.documents.commands.aprobar_para_markdown.
        AprobarParaMarkdown) debe haber verificado antes, via
        `application.governance.service.GovernanceService.
        verificar_documento_aprobable()`, que el documento no tiene
        incidencias criticas abiertas ni (si es critico) vigencia
        desconocida -- la MISMA regla que ya aplica RevisarDocumento,
        reutilizada aqui como segundo punto de control (Documento
        Maestro, seccion 4.7: la regla no se agota en la primera
        aprobacion). El registro `Aprobacion` (quien aprobo, cuando,
        comentario) lo crea y persiste quien llama, en su propio
        repositorio -- este metodo solo mueve el estado, mismo reparto
        de responsabilidades que `RevisarDocumento` con `Revision`."""
        return self.avanzar_a(EstadoDocumento.PENDIENTE_DE_APROBACION).avanzar_a(EstadoDocumento.APROBADO_PARA_MARKDOWN)

    def generar_markdown(self, ruta_markdown: str, hash_markdown: str) -> "Documento":
        """Modulo 12: fija la ruta y el hash del Markdown final de
        entrega y avanza APROBADO_PARA_MARKDOWN -> MARKDOWN_GENERADO en
        un solo paso atomico -- mismo principio que
        `completar_extraccion()`/`completar_normalizacion()`. Quien
        llama (application.documents.commands.generar_markdown.
        GenerarMarkdown) ya escribio el archivo en 07_markdown/ del
        proyecto y calculo su hash antes de invocar este metodo."""
        documento = self.avanzar_a(EstadoDocumento.MARKDOWN_GENERADO)
        data = documento.model_dump()
        data["ruta_markdown"] = ruta_markdown
        data["hash_markdown"] = hash_markdown
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def validar_markdown(self, advertencias: list[str] | None = None) -> "Documento":
        """Modulo 12: valida tecnicamente el Markdown ya generado y
        avanza MARKDOWN_GENERADO -> VALIDADO. Las advertencias (por
        ejemplo, "sin encabezados ni tablas Markdown") las calcula quien
        llama (application.documents.commands.validar_markdown.
        ValidarMarkdown, via domain.documents.estructura_markdown.
        tiene_estructura_markdown()) -- nunca bloquean esta transicion
        por si solas, mismo principio que advertencias_extraccion."""
        documento = self.avanzar_a(EstadoDocumento.VALIDADO)
        data = documento.model_dump()
        data["advertencias_markdown"] = advertencias or []
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def liberar(self) -> "Documento":
        """Modulo 12 + Modulo 13: avanza VALIDADO -> LIBERADO. Quien
        llama (application.documents.commands.liberar_documento.
        LiberarDocumento) debe haber verificado antes, via
        `GovernanceService.verificar_documento_liberable()`, que el
        documento tiene Fuente registrada y una Aprobacion guardada
        (Documento Maestro, seccion 4.7: "no liberar contenido sin
        fuente, hash y aprobacion") -- el hash de esa regla ya esta
        garantizado por construccion en este punto del flujo: no se
        puede llegar a VALIDADO sin haber pasado por
        `generar_markdown()`, que exige `hash_markdown`, ni existe un
        Documento sin `hash_sha256` (Modulo 3, campo obligatorio desde
        el registro). Una vez LIBERADO, `avanzar_a()` solo admite
        OBSOLETO -- "no sobrescribir una version aprobada" ya queda
        garantizado por la tabla de transiciones existente desde la
        Fase 1, sin necesidad de una regla nueva."""
        return self.avanzar_a(EstadoDocumento.LIBERADO)

    def asignar_a_lote(self, lote_id: str) -> "Documento":
        """Fase 7 (Lotes): fija `lote_id`, sin tocar `estado` en
        absoluto -- agrupar en un lote es ortogonal al avance por el
        flujo principal (Documento Maestro, seccion 4.7), a diferencia
        de `clasificar()`/`completar_extraccion()` (que sí colapsan un
        cambio de campo con una transicion de estado). Reemplaza
        cualquier asignacion anterior -- un documento pertenece, como
        maximo, a un solo lote a la vez. Las validaciones (que el lote
        exista y siga ABIERTO) las hace quien llama
        (application.batches.commands.agregar_documento_a_lote.
        AgregarDocumentoALote), no este metodo."""
        data = self.model_dump()
        data["lote_id"] = lote_id
        data["updated_at"] = _utcnow()
        return Documento(**data)

    def quitar_de_lote(self) -> "Documento":
        """Fase 7 (Lotes): vuelve a dejar `lote_id` en `None`. Mismo
        principio que `asignar_a_lote()`: no toca `estado`."""
        data = self.model_dump()
        data["lote_id"] = None
        data["updated_at"] = _utcnow()
        return Documento(**data)


class Revision(BaseModel):
    """Registro inmutable de una revision humana completada sobre un
    documento (Modulo 8, ADR-001 seccion 5: "documento_id, revisor,
    fecha, alcance revisado, incidencias detectadas"). A diferencia de
    `Documento` (que solo guarda el estado/ruta de su revision MAS
    RECIENTE), un documento puede acumular varias `Revision` a lo largo
    de su vida -- por ejemplo, si vuelve a EXTRAIDO tras una correccion
    y se revisa de nuevo -- y cada una queda en su propio registro con
    historial completo, nunca se sobrescribe.

    `incidencias_detectadas` es una fotografia de los ids de
    `domain.incidents.entities.Incidencia` que existian sobre el
    documento en el momento de completar ESTA revision -- no una
    relacion viva: si una incidencia se cierra despues, esta lista no
    cambia, porque describe lo que el revisor via en ese momento.
    `domain.documents` no importa `domain.incidents` para construir
    esta lista -- quien la resuelve es
    `application.documents.commands.revisar_documento.RevisarDocumento`,
    recibiendola ya armada (mismo principio que
    `NormalizarDocumento` con las reglas del perfil)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    documento_id: str
    revisor: str
    comentario: str = ""
    incidencias_detectadas: list[str] = Field(default_factory=list)
    fecha: datetime = Field(default_factory=_utcnow)

    @field_validator("revisor")
    @classmethod
    def _revisor_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El revisor no puede estar vacio")
        return v


class Aprobacion(BaseModel):
    """Registro inmutable de la aprobacion de un documento para generar
    su Markdown final (Modulo 12/13, Documento Maestro seccion 4.10:
    entidad "Aprobacion" del modelo de datos minimo). Mismo principio
    que `Revision`: un documento normalmente acumula una sola
    `Aprobacion` en la version actual del flujo (no existe hoy un
    camino de vuelta desde APROBADO_PARA_MARKDOWN a NORMALIZADO), pero
    se modela como historial -- nunca se sobrescribe -- por si una
    version futura permite reabrir un documento para una nueva ronda.

    Distinta de `Revision` (Modulo 8: cotejo contra el original) y de
    la aprobacion de "validation_status" de RAG STUDIO (seccion 4.6.1:
    "gobierno duplicado" -- son flujos de revision independientes, esta
    Aprobacion nunca se sincroniza hacia RAG STUDIO)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    documento_id: str
    aprobador: str
    comentario: str = ""
    fecha: datetime = Field(default_factory=_utcnow)

    @field_validator("aprobador")
    @classmethod
    def _aprobador_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El aprobador no puede estar vacio")
        return v


class ResultadoExtraccion(BaseModel):
    """Salida de un `DocumentExtractor` (Modulo 5): el Markdown
    normalizado (encabezados y tablas reales, sin YAML embebido --
    mismo contrato que el Modulo 12 exige para la entrega final a RAG
    STUDIO, seccion 4.6.1 del Documento Maestro) mas cualquier aviso no
    bloqueante."""

    markdown: str
    metodo: str
    """Como se obtuvo el texto (p. ej. 'docx', 'pdf_texto', 'xlsx',
    'csv', 'texto_plano', 'json') -- util para diagnostico, no afecta
    el flujo."""
    advertencias: list[str] = Field(default_factory=list)
    mapa_paginas: list[int] = Field(default_factory=list)
    """Modulo 8 (navegacion sincronizada real): desplazamientos en
    caracteres, dentro de `markdown`, donde empieza cada pagina del
    original -- ver Documento.mapa_paginas. Solo lo llenan
    PdfExtractor/PdfOcrExtractor; el resto de extractores lo deja
    vacio (formatos sin concepto de "pagina" navegable en este
    prototipo)."""
    rangos_baja_confianza: list[RangoBajaConfianza] = Field(default_factory=list)
    """Modulo 8 (agregado 2026-08-01): tramos de `markdown` que
    corresponden a palabras reconocidas por OCR con baja confianza --
    ver Documento.rangos_baja_confianza. Solo lo llenan
    PdfOcrExtractor/ImageOcrExtractor; el resto de extractores (sin OCR
    de por medio) lo deja vacio."""


class Segmento(BaseModel):
    """Un fragmento de audio/video ya transcrito (Modulo 7): la unidad
    minima que ADR-001 (seccion 4) exige poder representar --
    'segmentos, hablantes opcionales, marcas de tiempo, fragmentos
    inaudibles'. `hablante` queda en `None` en la primera version: el
    motor confirmado (Whisper local via faster-whisper, ADR-001 seccion
    14.1) no incluye diarizacion (identificacion de quien habla) -- se
    deja el campo listo para cuando se agregue esa capacidad, sin
    necesidad de otra migracion de este value object."""

    inicio_segundos: float
    fin_segundos: float
    texto: str
    hablante: Optional[str] = None
    inaudible: bool = False
    """True si el motor de transcripcion reporto muy baja confianza de
    que el segmento contenga voz reconocible (heuristica basada en
    no_speech_prob de Whisper) -- `texto` puede seguir teniendo un
    intento de transcripcion, pero no debe tratarse como confiable."""


class ResultadoTranscripcion(BaseModel):
    """Salida de un `TranscriptionEngine` (Modulo 7): lista ordenada de
    `Segmento`. Quien la consume (AudioVideoTranscriptionExtractor) la
    normaliza a Markdown con marcas de tiempo legibles, mismo contrato
    de salida que `ResultadoExtraccion` exige para 03_extracciones/ del
    proyecto (Documento Maestro, seccion 4.6.1)."""

    segmentos: list[Segmento] = Field(default_factory=list)


class ResultadoNormalizacion(BaseModel):
    """Salida de un `NormalizationEngine` (Modulo 9): el Markdown ya
    normalizado mas el registro transparente de cada cambio aplicado --
    Documento Maestro, seccion 4.6: "aplicar reglas sin alterar
    silenciosamente". Una regla que no tuvo efecto sobre el documento
    (por ejemplo, un patron de dato sensible que no aparece en el
    texto) simplemente no agrega nada a `cambios`; no es un error."""

    markdown_normalizado: str
    cambios: list[str] = Field(default_factory=list)


class FilaManifiesto(BaseModel):
    """Un renglon del manifiesto de entrega hacia RAG STUDIO (Modulo 12,
    Documento Maestro seccion 4.6.1: "contrato de salida confirmado con
    RAG STUDIO"). Las columnas y su nota corresponden exactamente a la
    tabla de esa seccion -- cada campo aqui es el nombre en espanol del
    manifiesto; `application.documents.commands.generar_manifiesto.
    GenerarManifiesto` es quien lo arma por documento, y
    `domain.documents.ports.ManifestWriter` quien lo escribe a disco
    (CSV) sin saber nada de Documento/Fuente/Vigencia.

    Contrato v2 (2026-09-29, incidencia real de portabilidad Windows ->
    macOS -- ver CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md):
    RAG STUDIO SI tiene hoy una via automatica ("Importar carpeta de RAG
    CONTENT...", RegisterSourcesFromFolder) que lee este manifiesto
    -- la premisa anterior de esta docstring ("ningun campo se lee
    automaticamente") quedo desactualizada respecto del codigo real de
    RAG STUDIO y se corrige aqui. Por eso `ruta_archivo` ya no puede ser
    una ruta absoluta del equipo productor (ver su campo mas abajo)."""

    titulo: str
    tipo_fuente: str
    """Siempre 'markdown' en esta version: el Modulo 12 entrega
    siempre el documento normalizado completo como archivo .md (seccion
    4.6.1, "estructura dentro del archivo"), sin importar el formato de
    entrada original del documento."""
    ruta_archivo: str
    """SOLO el nombre de archivo (p. ej. "c60369bd-....md"), NUNCA una
    ruta absoluta ni con separadores de carpeta -- es relativo a la
    carpeta que contiene este mismo manifiesto
    (`14_entrega_rag_studio/`). Antes de esta version contenia la ruta
    absoluta interna del equipo que genero el documento, lo cual
    impedia importar el paquete en un equipo distinto (incidencia real
    2026-09-29, Windows -> macOS: RAG STUDIO reporto "Importadas: 0" con
    los 13 .md fisicamente presentes en la carpeta de entrega)."""
    area_propietaria: str = ""
    nivel_acceso: str = ""
    idioma: str = "es"
    hash_contenido: str
    """Hash del Markdown final entregado (`Documento.hash_markdown`),
    no del archivo original (`hash_sha256`, Modulo 3) -- es el contenido
    que efectivamente se registraria como fuente en RAG STUDIO."""
    vigente_desde: Optional[str] = None
    vigente_hasta: Optional[str] = None
    autoridad_fuente: Optional[int] = None
    """Numero entero de prioridad (1 = maxima autoridad) -- distinto de
    `Vigencia.autoridad` (el nombre de la instancia/area responsable).
    Esta herramienta todavia no captura un ranking numerico de fuentes;
    queda vacio a proposito para que el operador lo complete dentro de
    RAG STUDIO si lo necesita (seccion 4.6.1: "vacio si no se
    prioriza")."""
    sustituye_a: Optional[str] = None
