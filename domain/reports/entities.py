"""Entidades del contexto Reportes (Fase 8 del orden aprobado
2026-07-28; Documento Maestro seccion 7.1: "Documentacion automatica que
debe producir la herramienta"). Cada clase de aqui es el renglon (o, en
el caso de `ActaCierreLote`, el documento completo) de exactamente una
de las filas de la tabla de esa seccion -- mismo principio que
`domain.documents.entities.FilaManifiesto` (Modulo 12): son value
objects puros, sin metodos de negocio ni validadores de "no vacio",
porque describen un HECHO ya calculado por application, no una entidad
que evoluciona por su propio ciclo de vida.

`domain.reports` no importa ningun otro paquete `domain.*` -- mismo
aislamiento estricto que el resto de contextos (`domain.incidents`,
`domain.validity`, `domain.governance`, `domain.jobs`, `domain.batches`).
Cada informe combina datos de varios contextos a la vez (por ejemplo, el
informe de procesamiento combina `Documento` y `Trabajo`), asi que quien
los arma es necesariamente `application.reports` (ver sus docstrings),
leyendo de varios repositorios directamente -- mismo patron de
acoplamiento cruzado ya usado por `GenerarManifiesto`/`CerrarLote`. Las
columnas de cada Fila usan solo tipos primitivos (str, int, bool, list de
esos) para no tener que importar ningun enum ni entidad de otro
contexto."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FilaInventario(BaseModel):
    """Un renglon del "Informe de inventario" (Documento Maestro,
    seccion 7.1: "Recibidos, formatos, areas, prioridades, duplicados,
    vigencias y estados"). No incluye una columna de "duplicados": el
    Modulo 3 (`application.documents.commands.registrar_documento.
    RegistrarDocumento`, via `DocumentRepository.get_by_hash()`) ya
    impide registrar dos documentos con el mismo hash SHA-256 -- el
    numero de duplicados en el inventario esta garantizado en 0 por
    construccion, no hay nada que contar (mismo tipo de razonamiento que
    "no cerrar un lote con documentos sin estado" en Fase 7)."""

    documento_id: str
    nombre_original: str
    formato: str
    area_propietaria: str
    prioridad: str
    criticidad: str
    estado: str
    vigencia: str
    """Uno de 'vigente', 'vencida', 'sin_vencimiento' o 'desconocida' --
    calculado por `application.reports.commands.
    generar_informe_inventario.GenerarInformeInventario` a partir de
    `domain.validity.entities.Vigencia`/`vigencia_desconocida()`, sin que
    este value object sepa nada de ese contexto."""


class FilaProcesamiento(BaseModel):
    """Un renglon del "Informe de procesamiento" (Documento Maestro,
    seccion 7.1: "Extracciones, OCR, audio, errores, reintentos y
    herramientas utilizadas"). `intentos_trabajo`/`estado_trabajo`
    provienen de `domain.jobs.entities.Trabajo` (Fase 6) cuando el
    documento se procesa por la cola en segundo plano; si nunca paso por
    ahi (por ejemplo, se proceso sincronicamente desde la GUI sin
    encolarlo), quedan en 0/'sin_trabajo_asociado' -- ausencia de
    trabajo, no un error."""

    documento_id: str
    tipo_procesamiento: str
    """Valor de `domain.documents.entities.TipoProcesamiento`, o
    'sin_clasificar' si el documento todavia no llego al Modulo 4."""
    herramienta: str
    """Nombre legible del motor/adaptador usado, derivado de
    `tipo_procesamiento` (por ejemplo, 'Tesseract (OCR)' o 'faster-whisper
    (transcripcion)') -- ver el mapeo en
    `application.reports.commands.generar_informe_procesamiento`."""
    advertencias: list[str] = Field(default_factory=list)
    """`Documento.advertencias_extraccion` completas (no solo la
    cantidad, corregido 2026-07-31 -- comentario real del consultor tras
    analizar una corrida completa: un informe que solo dice "1
    advertencia" sin decir CUAL no le sirve a quien esta auditando la
    calidad de un documento, tiene que ir a buscarla a otro lado. Vacio
    si no hubo ninguna."""
    intentos_trabajo: int
    """Suma de `Trabajo.intentos` de todos los trabajos de tipo
    EXTRACCION asociados a este documento -- 0 si nunca se encolo
    ninguno."""
    estado_trabajo: str
    """Estado del trabajo de tipo EXTRACCION mas reciente asociado a
    este documento, o 'sin_trabajo_asociado' si nunca se encolo
    ninguno."""


class FilaRevision(BaseModel):
    """Un renglon del "Informe de revision" (Documento Maestro, seccion
    7.1: "Documentos, responsables, fechas, cobertura y observaciones").
    Cada `domain.documents.entities.Revision` (Modulo 8) produce
    exactamente un renglon -- un documento revisado varias veces aparece
    varias veces, con su historial completo (mismo criterio de
    "nunca se sobrescribe" que la propia entidad Revision)."""

    documento_id: str
    revisor: str
    fecha: str
    """ISO 8601 (`Revision.fecha.isoformat()`)."""
    incidencias_detectadas: int
    """Cantidad de ids en `Revision.incidencias_detectadas` -- la
    "cobertura" de la revision se expresa aqui como cuantas incidencias
    se detectaron en esa pasada, no como un porcentaje (esta herramienta
    no mide "cobertura" en ningun otro lugar del codigo; inventar una
    metrica nueva solo para este informe seria una unidad sin respaldo
    en el resto del sistema)."""
    comentario: str


class FilaIncidencia(BaseModel):
    """Un renglon del "Reporte de incidencias" (Documento Maestro,
    seccion 7.1: "Abiertas, cerradas, criticas, vencidas, responsables,
    tipos y documentos")."""

    incidencia_id: str
    documento_id: str
    etapa: str
    tipo: str
    severidad: str
    estado: str
    responsable: str
    """Cadena vacia si todavia no se asigno (ver
    `Incidencia.responsable`, `None` hasta `asignar()`)."""
    abierta: bool
    """`domain.incidents.entities.Incidencia.esta_abierta()`."""
    vencida: Optional[bool] = None
    """Limite deliberado de esta version: `Incidencia` (Modulo 10) no
    tiene ningun campo de fecha limite/vencimiento -- solo `created_at`/
    `updated_at`. Sin ese dato no hay como calcular si una incidencia
    esta "vencida" sin inventar un plazo que el Documento Maestro no
    define. Se deja `None` ("no determinable en esta version") en vez de
    `False` (que afirmaria, incorrectamente, que ninguna incidencia esta
    vencida) -- agregar un `fecha_limite` real a `Incidencia` queda
    fuera de esta fase."""


class FilaCalidad(BaseModel):
    """Un renglon del "Informe de calidad" (Documento Maestro, seccion
    7.1: "Validaciones, incumplimientos, bloqueos y semaforo")."""

    documento_id: str
    estado: str
    advertencias_extraccion: list[str] = Field(default_factory=list)
    """`Documento.advertencias_extraccion` completas (no solo la
    cantidad, corregido 2026-07-31 -- mismo motivo que
    `FilaProcesamiento.advertencias`, ver su docstring). Vacio si no
    hubo ninguna."""
    advertencias_markdown: list[str] = Field(default_factory=list)
    """`Documento.advertencias_markdown` completas (mismo motivo que
    `advertencias_extraccion` de aqui arriba). Vacio si no hubo
    ninguna."""
    incumplimientos: list[str] = Field(default_factory=list)
    """Mensajes de `domain.governance.exceptions.FuenteFaltanteError`/
    `AprobacionFaltanteError` que el documento incumpliria HOY si se
    intentara liberar (via
    `GovernanceService.verificar_documento_liberable()`, reutilizada sin
    duplicar la regla) -- vacio si ya esta LIBERADO o si pasaria la
    verificacion sin problema."""
    semaforo: str
    """Uno de 'verde', 'amarillo' o 'rojo' -- ver el criterio exacto en
    `application.reports.commands.generar_informe_calidad.
    _calcular_semaforo()`."""


class FilaTrazabilidad(BaseModel):
    """Un renglon del "Informe de trazabilidad" (Documento Maestro,
    seccion 7.1: "Original, hash, extraccion, normalizacion, Markdown y
    aprobaciones")."""

    documento_id: str
    nombre_original: str
    hash_sha256: str
    ruta_extraccion: Optional[str] = None
    ruta_normalizado: Optional[str] = None
    ruta_markdown: Optional[str] = None
    hash_markdown: Optional[str] = None
    aprobador: Optional[str] = None
    """Aprobador de la `Aprobacion` mas reciente del documento, o `None`
    si todavia no tiene ninguna."""
    fecha_aprobacion: Optional[str] = None
    """ISO 8601 de esa misma `Aprobacion`, o `None`."""


class ActaCierreLote(BaseModel):
    """El "Acta de cierre de lote" (Documento Maestro, seccion 7.1:
    "Liberados, bloqueados, exclusiones, riesgos, aprobadores y
    version"). A diferencia de las seis Filas anteriores (un renglon por
    documento, muchos por informe), esta es un documento unico por lote
    -- por eso vive como un solo value object con listas adentro, no como
    una lista de filas."""

    lote_id: str
    nombre_lote: str
    fecha_cierre: Optional[str] = None
    """ISO 8601 de `Lote.cerrado_en` -- `Optional` solo por completitud
    de tipo (un acta nunca deberia generarse para un lote que no este
    CERRADO; ver `domain.reports.exceptions.LoteNoCerradoParaActaError`,
    que impide llegar aqui con `None`)."""
    liberados: list[str] = Field(default_factory=list)
    """ids de los documentos del lote que terminaron LIBERADO."""
    bloqueados: list[str] = Field(default_factory=list)
    """ids de los documentos del lote que terminaron BLOQUEADO."""
    exclusiones: list[str] = Field(default_factory=list)
    """ids de los documentos del lote que terminaron DESCARTADO --
    "excluidos" de la entrega, pero sin salir del lote."""
    riesgos: list[str] = Field(default_factory=list)
    """Una nota de riesgo por cada documento bloqueado, describiendo por
    que (por ejemplo, "doc-1: sin Fuente registrada") -- no un catalogo
    de riesgos de negocio separado, que esta herramienta no modela."""
    aprobadores: list[str] = Field(default_factory=list)
    """Nombres unicos de los aprobadores (`Aprobacion.aprobador`) de los
    documentos liberados de este lote."""
    version: str = "v1"
    """Version del ESQUEMA de esta acta (no del lote ni del documento) --
    fija en esta primera version de la herramienta; solo cambiaria si el
    contenido minimo del acta (seccion 7.1) cambiara en una revision
    futura del Documento Maestro."""
