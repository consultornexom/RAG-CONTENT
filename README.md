# RAG Content Studio Desktop

Plataforma local de escritorio para preparar contenidos trazables
destinados a procesos RAG, siguiendo el Documento Maestro v1.1 y el
ADR-001 (`DOCS PROYECTO/`).

**Fase 1 (Núcleo documental) — Hito H2, en construcción.** Este
esqueleto cubre:

- **Módulo 1 (administración de proyectos):** crear un proyecto,
  validar que su perfil existe, generar su estructura física de 13
  subcarpetas (Documento Maestro, sección 4.5), persistirlo en la base
  global y registrar el evento de auditoría correspondiente.
- **Módulo 2 (administrador de perfiles):** paquetes de perfil
  versionados e inmutables (`perfiles/<id>/<version>.yaml`), con campos
  de metadato tipados, catálogos cerrados y reglas de validación
  embebidas, publicación de nuevas versiones sin sobrescribir las
  anteriores, comparación entre versiones y una huella SHA-256 del
  paquete completo ("paquetes firmables", ADR-001 sección 8).
- **Módulo 3 (inventario documental con hash SHA-256):** registro de
  documentos originales con copia local inmutable en `01_originales/`
  del proyecto, cálculo de hash SHA-256 para deduplicar por contenido
  (no por nombre de archivo), y persistencia en una base propia por
  proyecto (`proyecto.db`, separada de `aplicacion.db`).
- **Módulo 4 (clasificación y enrutamiento):** decide, para cada
  documento ya inventariado, si le corresponde extracción directa, OCR
  o corrección manual — PDF con capa de texto real (`pypdf`) va a
  extracción directa, PDF sin texto o imágenes (PNG/JPG) van a OCR, un
  PDF ilegible (corrupto/cifrado) va a corrección manual. Transición
  `INVENTARIADO -> CLASIFICADO`.
- **Módulo 5 (extracción documental, formatos directos):** extrae y
  normaliza a Markdown real (encabezados `#`/`##`, tablas `| ... |`)
  los documentos que el Módulo 4 clasificó como extracción directa —
  TXT y Markdown (literal), JSON (bloque de código), DOCX (estilos
  `Heading N`/tablas), PDF con texto (`pypdf`), XLSX y CSV (una tabla
  por hoja/archivo). El resultado se guarda en `03_extracciones/` del
  proyecto. Transición `CLASIFICADO -> EN_EXTRACCION -> EXTRAIDO`.
- **Módulo 6 (OCR real, Tesseract):** extrae los documentos que el
  Módulo 4 enrutó a OCR — imágenes (PNG/JPG, siempre OCR) y PDF sin
  capa de texto (rasterizado página por página con PyMuPDF, `dpi=200`,
  y reconocido con Tesseract vía `pytesseract`, idioma por defecto
  `spa+eng`). `extraer_documento()` ya no rechaza la ruta OCR — la
  procesan `ImageOcrExtractor`/`PdfOcrExtractor`, cableados en
  `app.bootstrap.abrir_proyecto()` junto a los extractores de
  extracción directa del Módulo 5. Motor no disponible (binario o
  paquete de idioma ausente) se reporta como
  `OcrEngineUnavailableError`, nunca como un crash del proceso externo.
- **DOC/XLS legado:** `DocLegacyExtractor`/`XlsLegacyExtractor`
  convierten primero el archivo a DOCX/XLSX con LibreOffice en modo
  headless (`LibreOfficeConverter`, puerto `LegacyFormatConverter`,
  perfil de usuario temporal y exclusivo por llamada) y luego reusan
  `DocxExtractor`/`XlsxExtractor` (Módulo 5) sobre el archivo ya
  convertido. Conversión fallida (binario `soffice` ausente, archivo de
  entrada no reconocido, subproceso sin respuesta) se reporta como
  `LegacyConversionFailedError`. El directorio temporal de la
  conversión se borra siempre, éxito o fallo.
- **Módulo 7 (transcripción, audio/video):** confirmado 2026-07-28 —
  audio/video salen de "extensión posterior" y entran a la lista de
  formatos de la primera versión (Documento Maestro, sección 4.4).
  MP3/WAV/M4A (audio) y MP4/MOV (video) se enrutan siempre a
  TRANSCRIPCION (Módulo 4). `AudioVideoTranscriptionExtractor` convierte
  los `Segmento` (inicio/fin, texto, hablante opcional, marca de
  inaudible) que devuelve `TranscriptionEngine` a Markdown con marcas de
  tiempo legibles (`**[00:00:00 - 00:00:05]** texto...`). Adaptador
  confirmado: `FasterWhisperEngine` (Whisper local vía `faster-whisper`,
  ADR-001 sección 14.1, idioma por defecto `es`). Sin diarización en
  esta primera versión (`Segmento.hablante` siempre `None`) — el motor
  confirmado no la incluye; el campo queda listo para cuando se agregue.
  Motor no disponible (pesos no descargables/cargables, o archivo no
  decodificable) se reporta como `TranscriptionEngineUnavailableError`.
  El Markdown resultante se guarda en `04_transcripciones/` del
  proyecto — carpeta distinta de `03_extracciones/` (extracción
  directa/OCR), ya reservada desde el Módulo 1 (Documento Maestro,
  sección 4.5); `ExtraerDocumento` elige el `ExtractionOutputStore`
  correcto según la ruta de procesamiento del documento.
- **Módulo 9 (normalización, motor de reglas propio):** aplica, sobre
  el Markdown ya revisado (`Documento` en estado `REVISADO`), las
  reglas de normalización declaradas en el perfil del proyecto
  (`PerfilProyecto.reglas_normalizacion`, ADR-001 sección 8: "reglas en
  YAML por perfil"). `RuleBasedNormalizationEngine`
  (`domain.documents.ports.NormalizationEngine`) reconoce cinco tipos
  de regla en esta primera versión: `eliminar_linea_repetida`
  (encabezados/pies de página repetidos), `colapsar_saltos_de_linea`
  (3+ saltos consecutivos a un solo párrafo), `expandir_acronimo`
  (glosario aplicado una sola vez, en la primera aparición),
  `redactar_patron` (expresión regular -> `[DATO SENSIBLE REDACTADO]`)
  y `normalizar_espacios_en_tablas` (celdas de tabla Markdown). Una
  regla de tipo desconocido nunca se ignora en silencio: lanza
  `ReglaNormalizacionDesconocidaError` (Documento Maestro, sección 4.6:
  "aplicar reglas sin alterar silenciosamente"). El resultado se guarda
  en `06_normalizados/` del proyecto — carpeta distinta de
  `03_extracciones/`, igual que ya hace la transcripción con
  `04_transcripciones/`. Transición `REVISADO -> EN_NORMALIZACION ->
  NORMALIZADO`. Requiere que el documento ya esté `REVISADO`; como el
  Módulo 8 (revisión contra originales, requiere interfaz gráfica)
  todavía no existe, las pruebas avanzan el estado con el primitivo
  `Documento.avanzar_a()` directamente — normalización en sí no
  necesita el caso de uso real de revisión, solo el estado.
  `ReglaNormalizacion` (nueva entidad de `domain.profiles.entities`,
  consumida por `domain.documents.ports.NormalizationEngine`) es la
  primera referencia cruzada deliberada entre los contextos Perfiles y
  Documentos de este proyecto.
- **Módulo 10 (gestión de incidencias):** registra, asigna, responde,
  decide y cierra incidencias sobre un documento (Documento Maestro,
  sección 4.6: "Controlar dudas y defectos"; sección 4.11.1:
  "registrar, asignar, resolver o bloquear incidencias"). Entidad
  `Incidencia` (`domain.incidents.entities`) con campos `etapa`, `tipo`,
  `severidad`, `evidencia`, `impacto`, `responsable`, `estado`,
  `respuesta`, `decision` y `cierre` — exactamente los de la tabla de
  módulos (sección 4.6) — y un ciclo de vida lineal con una única
  bifurcación: `ABIERTA -> ASIGNADA -> RESPONDIDA -> (RESUELTA |
  BLOQUEADA) -> CERRADA`, sin saltos ni retrocesos
  (`InvalidIncidentStateTransitionError`). `RegistrarIncidencia` valida
  que el documento referenciado exista en el inventario del proyecto
  antes de crear la incidencia — única dependencia real hacia el
  contexto Documentos, resuelta en `application` (`domain.incidents` no
  importa `domain.documents`). `IncidentsService.existen_criticas_abiertas()`
  deja consultable si un documento tiene incidencias `CRITICA` todavía
  abiertas (`Incidencia.esta_abierta()`) — la aplicación real de la
  regla "incidencias críticas abiertas: 0" (Documento Maestro, sección
  8.2) para bloquear la aprobación es responsabilidad del Módulo 13
  (Estados y dependencias), todavía no construido; este módulo solo
  deja el dato registrado y consultable, sin bloquear nada por sí
  mismo. Persistencia propia en `proyecto.db` (tabla `incidencias`,
  separada de `documentos`).

- **Módulo 8 (revisión contra originales), completo (PySide6):**
  ventana principal (`ui.main_window.MainWindow`) con visor dual --
  panel "Original" (renderiza PDF página por página con PyMuPDF,
  muestra PNG/JPG directamente, texto plano para
  TXT/Markdown/JSON/CSV, y para el resto un botón "Abrir con la
  aplicación del sistema") y panel "Extraído / revisado". Panel de
  incidencias del documento seleccionado (Módulo 10) con botón
  "Registrar incidencia", y botón "Aprobar revisión" que llama al caso
  de uso `RevisarDocumento` (`DocumentsService.revisar_documento()`):
  `EXTRAIDO -> EN_REVISION -> REVISADO` en un solo paso atómico.
  Arranque: `python run_app.py` (o `python -m ui`, equivalente -- ver
  la sección "Interfaz gráfica" más abajo, incluye arranque maximizado
  tras la pantalla de bienvenida, mismo patrón que RAG STUDIO).

  Los tres pendientes que dejaba el primer prototipo (2026-07-28) ya
  están cerrados:
  - **Corrección editable y persistida:** nuevo campo
    `Documento.ruta_revisado` y método `Documento.corregir()` (Módulo
    8) -- guarda una nueva versión del Markdown SIN avanzar de estado
    (a diferencia de `completar_extraccion()`/`completar_normalizacion()`,
    puede llamarse varias veces mientras el documento sigue `EXTRAIDO`).
    Nuevo caso de uso `CorregirExtraccion`
    (`DocumentsService.corregir_extraccion()`), guarda en
    `05_revisiones/` del proyecto (carpeta dedicada, igual que
    `04_transcripciones/` para el Módulo 7). El panel "Extraído /
    revisado" se vuelve editable exactamente cuando el documento está
    `EXTRAIDO` (único estado en que `corregir()` lo permite) con un
    botón "Guardar corrección"; en cualquier otro estado queda de solo
    lectura (defensa en profundidad, mismo criterio que el botón
    "Aprobar revisión"). Nuevo método
    `Documento.ruta_markdown_vigente()` (normalizado -> corregido ->
    extraído en crudo) como única fuente de verdad de "qué Markdown
    mostrar/normalizar", usado tanto por la GUI como por
    `NormalizarDocumento`.
  - **Verificación de fechas/cifras:** nueva función pura
    `domain.documents.verificacion_fechas_cifras.detectar_fechas_y_cifras()`
    -- detecta (no valida) fechas en varios formatos (`DD/MM/AAAA`,
    ISO, y en español "12 de mayo de 2026") y cifras (moneda,
    porcentajes, separadores de miles) dentro del Markdown vigente, y
    las lista en un panel aparte con la posición donde aparecen; un
    clic en un hallazgo salta el cursor del panel de Markdown a esa
    posición para que el revisor lo coteje contra el original. La
    decisión de si está bien sigue siendo siempre del revisor.
  - **Navegación sincronizada real:** nuevo campo
    `Documento.mapa_paginas: list[int]` (y `ResultadoExtraccion.mapa_paginas`)
    -- desplazamiento en caracteres, dentro del Markdown, donde
    empieza cada página del original. Solo lo llenan `PdfExtractor` y
    `PdfOcrExtractor` (únicos extractores con concepto de "página");
    el resto de formatos lo deja vacío y la navegación simplemente no
    sincroniza, sin fallar. Cambiar de página del PDF original mueve
    el cursor del panel de Markdown al offset correspondiente.

  Ver `ui/main_window.py` (docstring) para el detalle completo.

  **Historial de revisiones (`Revision`, ADR-001 sección 5):** cada
  aprobación de revisión ya persiste su propio registro inmutable
  (`documento_id`, `revisor`, `comentario`, `fecha`,
  `incidencias_detectadas`) en una tabla dedicada (`revisiones`,
  separada de `documentos`) — a diferencia del evento de auditoría
  (que solo guarda revisor y motivo, sin historial estructurado por
  documento), un documento puede acumular varias `Revision` a lo largo
  de su vida y ninguna se sobrescribe. `incidencias_detectadas` es una
  fotografía de las incidencias abiertas del documento en el momento
  exacto de la aprobación (la ventana principal las resuelve
  consultando `IncidentsService.listar_incidencias_de_documento()`
  antes de llamar a `revisar_documento()`), no una relación viva.
  Nuevo puerto `domain.documents.ports.RevisionRepository` con su
  adaptador `infrastructure.database.revision_repository.
  SqlAlchemyRevisionRepository`; `DocumentsService.listar_revisiones()`
  expone el historial completo de un documento.

- **Módulo 13 (Estados y dependencias) — dos reglas reales de
  bloqueo.** `GovernanceService.verificar_documento_aprobable(documento_id)`
  (contexto acotado `domain.governance`/`application.governance`,
  nombre de paquete ya previsto en el ADR-001, sección 7) aplica dos
  reglas, en este orden:
  1. **No aprobar con incidencias críticas abiertas** (primera regla,
     2026-07-28). Hasta el Módulo 10, `IncidentsService.
     existen_criticas_abiertas()` solo dejaba el dato consultable; esta
     regla lo aplica de verdad, lanzando `IncidenciasCriticasAbiertasError`
     (mensaje en español simple, nunca un error técnico crudo — sección
     4.11.1) si el documento tiene al menos una incidencia crítica
     todavía abierta. Depende directamente de
     `domain.incidents.ports.IncidentRepository` (el puerto del otro
     contexto, no su fachada) — mismo patrón que ya usa
     `RegistrarIncidencia`. El criterio "incidencia crítica y abierta"
     se extrajo a una función pura
     (`domain.incidents.entities.filtrar_criticas_abiertas()`) para que
     `IncidentsService` y `GovernanceService` no lo dupliquen.
  2. **Bloquear documentos críticos con vigencia desconocida**
     (segunda regla, 2026-07-28, apoyada en el Módulo 11 ya completo).
     A diferencia de la primera regla, esta SOLO aplica si
     `Documento.criticidad == Criticidad.CRITICO` — un documento no
     crítico puede aprobarse aunque su vigencia todavía no se haya
     registrado (Documento Maestro, sección 4.7). Lanza
     `VigenciaDesconocidaError` si el documento es crítico y
     `domain.validity.entities.vigencia_desconocida()` (Módulo 11)
     regresa `True` para su `Vigencia` (sin registrar, o registrada de
     forma incompleta). Depende directamente de
     `domain.validity.ports.VigenciaRepository` y de
     `domain.documents.ports.DocumentRepository` (para resolver la
     `criticidad` del documento) — mismo principio de acoplamiento
     cruzado resuelto en `application`, nunca en `domain`.

  `RevisarDocumento` llama a esta verificación ANTES de mutar el
  estado del documento — si cualquiera de las dos reglas bloquea, ni
  el documento ni la `Revision` cambian. `domain.governance` no importa
  `domain.incidents`/`domain.documents`/`domain.validity` en absoluto;
  ese cruce se resuelve siempre en `application.governance`. La
  ventana principal también deshabilita el botón "Aprobar revisión" de
  forma proactiva cuando cualquiera de las dos reglas bloquearía,
  además del bloqueo real en `application` (defensa en profundidad: la
  regla de negocio nunca vive solo en la interfaz) — el panel "Vigencia
  y fuente" deja registrar la vigencia sin salir de la ventana, y el
  botón "Aprobar revisión" se habilita de inmediato si eso resuelve el
  bloqueo.

- **Módulo 11 (Vigencias y fuentes).** Nuevo contexto acotado
  `domain.validity`/`application.validity`, con dos entidades
  independientes -- `Fuente` (`documento_id`, `sistema_origen`,
  `autoridad`, `evidencia_consulta`) y `Vigencia` (`documento_id`,
  `fecha_emision`, `vigente_desde`/`vigente_hasta`, `sin_vencimiento`,
  `autoridad`, `sustituye_a`) -- exactamente el modelo de datos del
  ADR-001 (sección 5): "Separa explícitamente vigencia, validación y
  autoridad -- no deben confundirse". A lo sumo un registro de cada una
  por documento (`documento_id` es la clave primaria en sí, sin un
  `id` sintético). `sin_vencimiento` distingue explícitamente "vigente
  sin fecha de vencimiento conocida" de "todavía no se investigó" --
  la función pura `domain.validity.entities.vigencia_desconocida()`
  usa esa distinción para decidir si una vigencia cuenta como
  "conocida" o no, mismo principio que
  `filtrar_criticas_abiertas()` (Módulo 10): se define una sola vez
  y la reutiliza el Módulo 13 (segunda regla, ver más arriba) sin
  duplicarla. `RegistrarFuente`/`RegistrarVigencia` validan contra
  `DocumentRepository` que el documento (y, si aplica, el
  `sustituye_a`) existan en el inventario -- mismo patrón de
  acoplamiento cruzado que `RegistrarIncidencia`. Ambos casos de uso
  son upsert, no alta estricta: el flujo real es "confirmar o corregir"
  (Documento Maestro, sección 4.11: paso 9), no "registrar una sola
  vez". Persistencia propia en `proyecto.db` (tablas `fuentes` y
  `vigencias`, cada una con `documento_id` como clave primaria). Panel
  mínimo en la ventana principal ("Vigencia y fuente", con botón
  "Registrar / actualizar") -- el asistente por etapas completo
  (sección 4.11) queda para la Fase 11 del orden aprobado.

- **Módulo 12 (Generador de Markdown), backend completo (2026-07-28).**
  Cierra el flujo principal hasta LIBERADO: `NORMALIZADO ->
  PENDIENTE_DE_APROBACION -> APROBADO_PARA_MARKDOWN -> MARKDOWN_GENERADO
  -> VALIDADO -> LIBERADO` (Documento Maestro, sección 4.7). Sin GUI en
  esta fase -- mismo criterio que el Módulo 9 (normalización), que
  también se entregó backend-only: la interfaz completa (asistente por
  etapas) es la Fase 11 del orden aprobado, y espera a que todos los
  backends existan primero.
  - **`AprobarParaMarkdown`** colapsa `NORMALIZADO ->
    PENDIENTE_DE_APROBACION -> APROBADO_PARA_MARKDOWN` en un solo paso
    atómico (mismo principio que `RevisarDocumento`), guarda un
    registro `Aprobacion` (nueva entidad, mismo patrón que `Revision` --
    historial inmutable, tabla `aprobaciones` propia) y **reutiliza sin
    duplicar** la misma verificación de `GovernanceService` que ya usa
    `RevisarDocumento` (incidencias críticas / vigencia desconocida) --
    Documento Maestro, sección 4.7: la regla aplica en cada punto de
    aprobación, no solo en el primero.
  - **`GenerarMarkdown`** copia el Markdown vigente (`Documento.
    ruta_markdown_vigente()`) hacia `07_markdown/` del proyecto -- carpeta
    de entrega final, distinta de `06_normalizados/` (trabajo interno) --
    y calcula `hash_markdown` (SHA-256 del contenido entregado, distinto
    de `hash_sha256` del archivo original). El estado se valida ANTES de
    escribir nada (a diferencia de otros casos de uso de este proyecto,
    aquí no hay un estado intermedio `EN_...` al que avanzar primero).
  - **`ValidarMarkdown`** rechaza un Markdown final vacío
    (`MarkdownVacioError`) y registra, sin bloquear, una advertencia si
    el documento no tiene ningún encabezado ni tabla Markdown real
    (nueva función pura `domain.documents.estructura_markdown.
    tiene_estructura_markdown()`) -- sección 4.6.1: RAG STUDIO fragmenta
    por encabezado o por tabla; sin esa estructura, tratará el documento
    como un solo bloque.
  - **`LiberarDocumento`** aplica la tercera regla real del Módulo 13:
    "no liberar contenido sin fuente, hash y aprobación" (sección 4.7).
    El "hash" de esa regla queda garantizado por construcción (no se
    llega a VALIDADO sin `hash_markdown`, ni existe un `Documento` sin
    `hash_sha256`); `GovernanceService.verificar_documento_liberable()`
    (nuevo, depende de `FuenteRepository`/`AprobacionRepository`)
    verifica los otros dos y lanza `FuenteFaltanteError`/
    `AprobacionFaltanteError` si faltan. Una vez `LIBERADO`, la tabla de
    transiciones ya existente desde la Fase 1 solo admite `OBSOLETO` --
    "no sobrescribir una versión aprobada" no necesitó una regla nueva.
  - **`GenerarManifiesto`** arma el manifiesto de entrega hacia RAG
    STUDIO (sección 4.6.1: contrato de salida confirmado por inspección
    directa de su código fuente) -- un renglón por documento `LIBERADO`
    del proyecto, con las columnas exactas de esa sección
    (`titulo`, `tipo_fuente` -- siempre `"markdown"` --, `ruta_archivo`,
    `area_propietaria`, `nivel_acceso`, `idioma`, `hash_contenido` --el
    del Markdown final, no el del original--, `vigente_desde`/
    `vigente_hasta`, `autoridad_fuente` --vacío: esta herramienta no
    captura un ranking numérico de fuentes-- y `sustituye_a`). Se
    entrega como CSV en `12_exportaciones/manifiesto.csv`
    (`CsvManifestWriter`), regenerado por completo cada vez (nunca
    acumula). Alcance deliberado de esta fase: "de todo el proyecto
    liberado", no "por lote" -- el contexto `Lote` todavía no existe
    (Fase 7 del orden aprobado). RAG STUDIO no lee este archivo
    automáticamente: es solo una ayuda para que el operador transcriba
    los valores más rápido al registrar la fuente a mano (sección
    4.6.1: "no existe todavía una vía automática entre las dos
    herramientas").

- **Colas de trabajo y workers aislados, Fase 6 (2026-07-28).** Nuevo
  contexto `domain.jobs`/`application.jobs` y nueva capa `workers/`
  (ADR-001, sección 3: "workers -- hilos/procesos/colas en 2do plano";
  sección 10: "Concurrencia y gestión de trabajos"). `domain.jobs` no
  importa `domain.documents` en absoluto -- mismo aislamiento estricto
  que el resto de contextos.
  - **`Trabajo`** (entidad "TrabajoProcesamiento" del modelo de datos
    mínimo, sección 4.10) con los siete estados exactos de ADR-001,
    sección 10 (`pendiente`, `preparando`, `ejecutando`, `pausado`,
    `completado`, `fallido`, `cancelado`) y su propia máquina de
    transiciones. Decisión documentada: `ejecutando` NO admite pausa ni
    cancelación -- los casos de uso pesados que un trabajo invoca
    (`extraer_documento`/`normalizar_documento`/`generar_markdown`) son
    llamadas síncronas atómicas sin punto de control interno; fingir una
    "cancelación segura" a la mitad sería el fallo silencioso que el
    Documento Maestro (sección 4.1) prohíbe. La cancelación real y seguro
    solo aplica a `pendiente`/`preparando`/`pausado` -- ningún caso de
    uso se invocó todavía.
  - **`EncolarTrabajo`** valida que el documento exista antes de
    encolar (mismo patrón de acoplamiento cruzado que
    `RegistrarIncidencia`). Ocho casos de uso más cubren el resto del
    ciclo de vida (`IniciarPreparacion`, `IniciarEjecucion`,
    `CompletarTrabajo`, `FallarTrabajo` -- incrementa `intentos` --,
    `PausarTrabajo`, `ReanudarTrabajo`, `CancelarTrabajo`,
    `ReintentarTrabajo` -- bloqueado por `ReintentosAgotadosError` si ya
    se agotó `max_intentos`) más `RecuperarTrabajosInterrumpidos`
    ("recuperación", sección 4.1): al abrir un proyecto, cualquier
    trabajo huérfano en `preparando`/`ejecutando` (porque la aplicación
    se cerró sin terminarlo) se marca `fallido` con un mensaje explícito
    -- nunca se asume que terminó, nunca queda fantasma para siempre.
  - **`ColaDeTrabajos`** (nueva capa `workers/`, depende de
    `application`/`infrastructure`, nunca de `ui`): modo síncrono
    determinista (`procesar_siguiente()`/`procesar_todos_los_pendientes()`,
    el que usan las pruebas) y modo en segundo plano real
    (`iniciar()`/`detener()`, `ThreadPoolExecutor` acotado a
    `max_trabajos_concurrentes`). Control de recursos (sección 4.8):
    sin cgroups ni límites de CPU/memoria por sistema operativo --fuera
    de alcance para una herramienta de escritorio de uso personal,
    confirmado 2026-07-28 en el Anexo B--, el control real y verificable
    es el límite de concurrencia del propio `ThreadPoolExecutor`.
  - Persistencia propia (`SqlAlchemyTrabajoRepository`, tabla
    `trabajos`, nueva migración) con `list_pendientes_por_prioridad()`
    (URGENTE primero, FIFO dentro de la misma prioridad). Sin GUI en
    esta fase -- mismo criterio que los Módulos 9 y 12: el panel de
    monitoreo de trabajos queda para la Fase 11.

- **Lotes, Fase 7 (2026-07-28).** Nuevo contexto `domain.batches`/
  `application.batches` (Documento Maestro, sección 4.10: entidad
  "Lote" del modelo de datos mínimo; sección 10.1, "Flujo operativo
  completo por lote", etapa 14: "Liberar aprobados, bloquear
  pendientes, firmar acta y exportar" -> "Lote cerrado"). `domain.batches`
  no importa `domain.documents` en absoluto; la relación vive del lado
  de `Documento.lote_id` (nuevo campo, nunca una lista de ids dentro de
  `Lote`).
  - **`Lote`**: solo dos estados, `ABIERTO`/`CERRADO` -- `CERRADO` es
    terminal, no existe hoy un caso de uso para reabrir un lote.
  - **`CrearLote`**, **`AgregarDocumentoALote`**/**`QuitarDocumentoDeLote`**
    (validan que el lote exista y siga `ABIERTO`, y que el documento
    exista -- mismo patrón de acoplamiento cruzado que
    `RegistrarIncidencia`/`EncolarTrabajo`) y **`CerrarLote`** (el caso
    de uso central): por cada documento del lote, si está `VALIDADO`
    intenta liberarlo de verdad (reutiliza la misma verificación de
    `GovernanceService.verificar_documento_liberable()` que usa
    `LiberarDocumento`, nunca la duplica); si no se puede liberar, o si
    todavía está en una etapa temprana, lo bloquea
    (`Documento.avanzar_a(BLOQUEADO)`); los que ya están
    `LIBERADO`/`BLOQUEADO`/`DESCARTADO`/`OBSOLETO` no se tocan. "No
    cerrar un lote con documentos sin estado" (sección 4.7) ya está
    garantizado por construcción (`Documento.estado` nunca es `None`) --
    mismo hallazgo que el hash en la tercera regla del Módulo 13; el
    único guardia nuevo es `LoteVacioError` (no se puede cerrar un lote
    sin ningún documento asociado). "Firmar acta y exportar" queda para
    la Fase 8.
  - **`GenerarManifiesto`** (Módulo 12) ya admite un `lote_id` opcional:
    sin él, incluye todo documento `LIBERADO` del proyecto
    (comportamiento sin cambios desde la Fase 5); con él, solo los
    `LIBERADO` de ese lote -- exactamente la extensión que se anticipó
    al construir el Módulo 12, ahora posible porque `Lote` ya existe.
  - Persistencia propia (`SqlAlchemyLoteRepository`, tabla `lotes`,
    columna `lote_id` nueva en `documentos`, misma migración). Sin GUI
    en esta fase -- mismo criterio que los Módulos 9, 12 y la Fase 6.

- **Reportes y documentación automática, Fase 8 (2026-07-29).** Nuevo
  contexto `domain.reports`/`application.reports` (Documento Maestro,
  sección 7.1: "Documentación automática que debe producir la
  herramienta"). Sin persistencia propia -- ningún informe se guarda en
  `proyecto.db`: cada uno se recalcula a partir de los repositorios ya
  existentes (Documento, Trabajo, Revisión, Incidencia, Aprobación,
  Lote) y se escribe siempre a los mismos siete archivos dentro de
  `10_reportes/` del proyecto (carpeta reservada desde la Fase 1, sin
  uso real hasta ahora).
  - Seis informes tabulares en CSV, uno por fila de la tabla de la
    sección 7.1: **inventario** (recibidos, formatos, áreas,
    prioridades, vigencias y estados -- sin columna de duplicados: el
    Módulo 3 ya los impide por construcción), **procesamiento**
    (herramienta usada, advertencias, e intentos/estado del `Trabajo`
    de extracción asociado, si lo hay -- primer informe que cruza
    datos de la Fase 6), **revisión** (historial completo de
    `Revision`, no solo la más reciente), **incidencias** (todo el
    catálogo, con una columna `vencida` deliberadamente vacía: `Incidencia`
    no tiene ningún campo de fecha límite en esta versión),
    **calidad** (reutiliza
    `GovernanceService.verificar_documento_liberable()` para listar
    incumplimientos reales sin duplicar la regla, y deriva un semáforo
    verde/amarillo/rojo) y **trazabilidad** (original, hash,
    extracción, normalización, Markdown y la aprobación más reciente).
  - **Acta de cierre de lote**, en Markdown, uno por lote (no se
    sobrescriben entre sí). Caso de uso separado de `CerrarLote`
    (Fase 7) a propósito -- mismo principio que `GenerarManifiesto` es
    un paso explícito distinto de `LiberarDocumento` -- así que puede
    volver a generarse sin repetir el cierre. Exige que el lote ya
    esté `CERRADO` (`LoteNoCerradoParaActaError` en caso contrario).
  - `ReportsService.generar_todos_los_informes()`: conveniencia para un
    futuro botón único de la GUI (Fase 11) que junta los seis informes
    de todo el proyecto en una sola llamada.
  - Sin GUI en esta fase -- mismo criterio que Módulos 9/12 y Fases 6/7.

- **Pruebas de aceptación sobre datos reales, Fase 9 (2026-07-29).**
  Nuevo contexto `domain.acceptance`/`application.acceptance`
  (Documento Maestro, sección 8.1 "Pruebas mínimas por dominio" y
  sección 8.2 "Umbrales recomendados de liberación"; Anexo B,
  confirmado 2026-07-28: "el usuario ya cuenta con archivos de prueba
  representativos"). Deliberadamente **distinta de la suite de
  `pytest`** de este propio código (que verifica que el código
  funciona): esta corre el flujo real y completo -- registro,
  clasificación, extracción, revisión, normalización, fuente, vigencia,
  aprobación, Markdown, validación, liberación, lote y acta de cierre
  (Fase 7/8) -- sobre un corpus de documentos reales, no sintéticos, y
  el resultado que importa es un informe humano-legible que una persona
  revisa, no un pass/fail de CI.
  - `EjecutarPruebasDeAceptacion` procesa cada archivo de
    `corpus_aceptacion/documentos/` (cualquier formato, sin necesidad de
    clasificarlos por carpeta: el propio Módulo 4 decide la ruta) y
    evalúa los siete dominios de la sección 8.1 más los seis umbrales
    de la sección 8.2, contando datos reales (no simulados). Un archivo
    que falle en cualquier paso (por ejemplo, sin el motor de
    transcripción disponible) no aborta la corrida completa: queda
    registrado con su error, excluido de los pasos posteriores.
  - Un dominio sin corpus todavía (por ejemplo, OCR sin ningún PDF
    escaneado) se marca `PENDIENTE`, nunca `FALLA` -- `InformeAceptacion.
    aprobado()`/`esta_completo()` distinguen "sin hallazgos" de "corpus
    completo", a propósito.
  - `scripts/ejecutar_pruebas_aceptacion.py`: punto de entrada manual
    (nunca automático ni expuesto a la GUI), usa una raíz aislada propia
    (`corpus_aceptacion/_runtime/`) para no mezclar los proyectos de
    prueba con los datos reales del consultor. El informe se escribe en
    `corpus_aceptacion/informes/`, archivado por corrida (nunca se
    sobrescribe).
  - Corrida real ejecutada 2026-07-29 contra
    `plan_estudios_electromecanica.pdf` (el archivo real confirmado en
    el Anexo B): **APROBADO**, con los seis umbrales de la sección 8.2
    cumplidos. Los dominios OCR, transcripción y legado (DOC/XLS)
    quedan `PENDIENTE` -- el corpus real cubre hoy la ruta de extracción
    directa; agregar más archivos representativos no requiere tocar
    ningún código (ver `corpus_aceptacion/README.md`).

- **Seguridad y distribución, Fase 10 (2026-07-29).** Nuevo contexto
  `domain.security`/`application.security` (Documento Maestro, sección 9
  "Riesgos, restricciones y cumplimiento" -- plan de mitigación:
  "Respaldos cifrados y pruebas de restauración"; ADR-001, sección 14.3
  "Política de seguridad"). Alcance confirmado en el Anexo B
  (2026-07-28): simplificado a lo estrictamente necesario para uso
  personal -- cifrado de respaldos y manual de operación propio, sin
  empaquetado/instalador ni actualizaciones automáticas.
  - **Respaldos cifrados**: `SecurityService.crear_respaldo()` empaqueta
    la carpeta completa del proyecto en un zip y lo cifra con Fernet
    (`cryptography`, cifrado simétrico autenticado) dentro de
    `13_respaldos/` (carpeta reservada desde la Fase 1, sin uso real
    hasta ahora). La clave se guarda en el almacén de credenciales del
    sistema operativo vía `keyring` (`KeyringCredentialStore`, mismo
    puerto y mismo adaptador que RAG STUDIO, ADR-001 sección 14.1) --
    nunca junto al archivo que protege, nunca en texto plano, nunca en
    un log.
  - **Pruebas de restauración**: `SecurityService.restaurar_respaldo()`
    descifra y desempaqueta un respaldo -- una clave incorrecta o un
    archivo corrupto/alterado se reporta como `RestauracionRespaldo.
    exitosa=False` con el detalle, nunca como una excepción de
    programación (mismo criterio de "pendiente/fallido no es un error de
    código" que la Fase 9). Incluye verificación explícita contra "zip
    slip" (rutas que escaparían de la carpeta de destino) antes de
    extraer cualquier contenido.
  - **Borrado seguro de temporales**: el zip intermedio sin cifrar (el
    único archivo de toda esta herramienta con el contenido completo de
    un proyecto en texto claro, fuera de su carpeta original) se
    sobrescribe con bytes aleatorios antes de eliminarse, no solo se
    borra con `shutil.rmtree` como el resto de temporales sin ese nivel
    de sensibilidad (por ejemplo, los de `LibreOfficeConverter`).
  - **Niveles de acceso** (público/interno/confidencial/restringido):
    ya existían desde la Fase 1 como `NivelConfidencialidad` en
    `domain.projects` -- no se duplica nada nuevo, solo se documenta la
    cobertura en el manual de operación.
  - `scripts/gestionar_respaldos.py`: punto de entrada manual
    (`listar`/`crear`/`restaurar`), ya que la GUI (Fase 11) todavía no
    tiene una pantalla para esto. A diferencia de
    `scripts/ejecutar_pruebas_aceptacion.py` (Fase 9), opera sobre la
    ruta raíz real: crear o restaurar el respaldo de un proyecto que no
    existe no tiene sentido.
  - Manual de operación propio en `MANUAL_OPERACION.md` (respaldo,
    restauración, gestión de la clave de cifrado, y qué hacer si se
    pierde el acceso al almacén de credenciales).
  - Sin GUI en esta fase -- mismo criterio que Módulos 9/12 y Fases 6/7/8.

- **Interfaz completa, Fase 11 (2026-07-29) -- "menú funcional primero".**
  Documento Maestro, sección 4.11, especifica tres piezas: menú
  funcional (12 áreas), asistente guiado por etapas, y pantalla
  principal tipo dashboard. Dado el tamaño frente a cualquier fase
  anterior, se decidió explícitamente (elección del consultor) construir
  primero el menú funcional completo y dejar el asistente y la pantalla
  principal para una pasada posterior -- mismo criterio incremental con
  el que se construyó el propio Módulo 8 (Fases 2.1/2.2/2.3).
  - **Menú funcional (12 áreas), completo.** `ui/main_window.py` ahora
    tiene una barra de navegación (`QListWidget` + `QStackedWidget`) con
    las 12 páginas de la sección 4.11: Proyectos, Inventario,
    Procesamiento, Revisión (Módulo 8, sin cambios), Normalización,
    Incidencias, Vigencias, Markdown, Pruebas de aceptación, Reportes,
    Auditoría y Configuración. Las últimas 8 conectan capacidades que ya
    existían en `application/*` desde fases anteriores pero nunca habían
    tenido una pantalla propia (colas de trabajo, lotes, reportes,
    pruebas de aceptación, normalización, generación de Markdown,
    perfiles, respaldos).
  - **Brecha de backend cerrada:** `AuditLogger` solo tenía escritura
    (`record()`) desde la Fase 1 -- se agregó `list_by_project()` (puerto
    + adaptador SQLAlchemy) porque la pantalla "Auditoría" no podía
    mostrar nada sin una forma de leer de vuelta lo que ya se escribía.
    No es una regla de negocio nueva, solo hace visible un dato que ya
    existía.
  - **Bug real encontrado y corregido durante las pruebas de humo:** las
    pantallas de Procesamiento, Incidencias y Markdown recargaban su
    tabla por completo después de cada acción (aprobar, clasificar,
    asignar...), perdiendo la fila seleccionada -- el siguiente paso de
    una cadena (por ejemplo, aprobar → generar → validar → liberar, o
    asignar → responder → decidir → cerrar) no hacía nada porque ya no
    había ninguna fila seleccionada. Se corrigió preservando la
    selección a través del recargue en las cuatro pantallas afectadas
    (Procesamiento, Incidencias, Markdown y, por consistencia,
    Normalización) -- viola directamente el principio de "baja fricción"
    de la sección 4.11.1 si no se corrige.
  - **Deliberadamente fuera de esta pasada:** el asistente guiado por
    etapas (vista predeterminada según la sección 4.11.1) y la pantalla
    principal tipo dashboard. La pantalla de Procesamiento, por ahora,
    también hace de "modo avanzado" (colas, cola de trabajos) visible
    sin el interruptor que la sección 4.11.1 describe -- no se construyó
    ese interruptor en esta pasada.
  - **Calidad:** Ruff ahora es obligatorio también sobre `ui/` y
    `scripts/` en el pre-commit (tabla 8.3 del Documento Maestro exige
    esto explícitamente para la capa de interfaz gráfica, a diferencia
    de Mypy/Bandit, que ahí siguen siendo incrementales por decisión ya
    tomada). Ruff, Mypy y Bandit limpios; `pip-audit` solo con el ruido
    habitual de paquetes del sistema operativo de este entorno de
    pruebas (no dependencias del proyecto). 515 pruebas unitarias +
    16 pruebas de humo (incluidas 4 nuevas de punta a punta sobre el
    menú completo) -- todas en verde. Cobertura total: 91.99% (piso:
    90%; `ui/` queda fuera de la medición de cobertura, mismo criterio
    ya establecido para Mypy/Bandit).

- **Asistente guiado por etapas, Fase 11.2 (2026-07-29).** Segunda
  pasada de la Fase 11: `ui.wizard.AsistenteWidget` pasa a ser la vista
  predeterminada al abrir la ventana (Documento Maestro seccion 4.11.1:
  "el asistente por etapas es la vista predeterminada al abrir un
  proyecto; el modo avanzado -- colas, logs, configuracion fina -- queda
  oculto detras de un interruptor explicito"). El menu completo de la
  primera pasada de la Fase 11 no se elimino ni se duplico: paso a ser
  ese "modo avanzado", detras de una casilla explicita
  ("Modo avanzado (menu completo)") junto al selector de proyecto.
  - **Diez pantallas para las doce etapas del Documento Maestro** (dos
    fusiones deliberadas y documentadas, no una omision: "crear
    proyecto" + "seleccionar perfil" en una sola etapa, porque
    `ProjectsService.crear_proyecto()` exige el perfil desde el momento
    de crear -- mismo criterio que `RegistrarVigenciaDialog` combinando
    Fuente y Vigencia; e "importar fuentes" + "completar inventario" en
    una sola etapa, porque en la practica son la misma pantalla).
  - **Reutiliza sin duplicar:** las etapas "Importar y completar
    inventario", "Resolver incidencias" y "Ejecutar pruebas" embeben
    directamente `InventarioPanel`/`IncidenciasPanel`/`PruebasPanel`
    (sin cambios). La etapa "Procesar" NO reutiliza `ProcesamientoPanel`
    a proposito -- ese panel tambien hace de "modo avanzado" (cola de
    trabajos), y meterlo aqui filtraria justo lo que el interruptor esta
    pensado para ocultar por defecto; en su lugar, tiene su propia
    accion por lotes ("clasificar y extraer todos los pendientes"),
    igual que Normalizar/Aprobar/Generar Markdown. Las etapas "Revisar"
    y "Cerrar lote" (para el acta) usan un enlace directo que activa el
    interruptor y navega a la pantalla del menu correspondiente
    (Revision necesita mas espacio del que tiene una etapa: vista previa
    de PDF, verificacion de fechas/cifras y navegacion sincronizada).
  - **Sesiones recuperables** (seccion 4.11.1): la etapa actual se
    autoguarda en un archivo `.asistente_estado.json` dentro de la
    propia carpeta del proyecto (mismo criterio de "todo lo del proyecto
    viaja con su carpeta" que respaldos/reportes) -- si la aplicacion se
    cierra sin avisar, al reabrir el proyecto el asistente vuelve
    exactamente a la etapa donde se habia quedado. Es codigo nuevo de
    presentacion (`ui.wizard.estado_asistente`), no una regla de negocio
    ni una tabla nueva en `proyecto.db`.
  - Navegacion: los botones "Atras"/"Siguiente" avanzan de a una etapa;
    la lista de etapas de la izquierda permite volver a cualquiera ya
    alcanzada, pero no saltar hacia adelante sin pasar por las
    intermedias (no tiene sentido "normalizar" antes de haber revisado).
  - Ruff limpio sobre `ui/wizard/` (mismo alcance obligatorio que el
    resto de `ui/` desde la Fase 11). 563 pruebas automatizadas en
    total (515 unitarias + 48 de humo, incluidas 4 nuevas de punta a
    punta sobre el asistente completo), ~97.6% de cobertura combinada
    (piso: 90%).
- **Pantalla principal (dashboard), Fase 11.3 (2026-07-29).** Tercera y
  ultima pasada de la Fase 11: `ui.dashboard.PantallaPrincipalWidget`
  cubre los ocho campos exactos de la seccion 4.11 ("Proyectos
  recientes, documentos por estado, trabajos en ejecución, incidencias
  críticas, documentos bloqueados, avance por lote, almacenamiento
  disponible y últimas actividades"), sin agregar ninguna tabla ni
  metodo nuevo a `application/*` -- es pura agregacion de datos que ya
  existian (con una sola excepcion menor: "almacenamiento disponible"
  usa `shutil.disk_usage()` directo sobre `Proyecto.ruta_carpeta`, una
  consulta al sistema operativo sin logica de negocio, mismo criterio
  ya usado por `ui.panels.configuracion_panel`/`pruebas_panel` leyendo
  esa misma ruta con `pathlib`).
  - **Es la vista de entrada** de la ventana (indice 0 de
    `self.modo_stack`, delante del asistente y del menu completo). El
    selector de modo pasa de una casilla a tres opciones excluyentes
    ("Inicio", "Asistente", "Modo avanzado (menu completo)"). Abrir o
    crear un proyecto desde cualquier lado (barra superior, doble clic
    en un proyecto reciente del dashboard, o la etapa 1 del asistente)
    pasa automaticamente a "Asistente" -- pero solo si el operador
    estaba en "Inicio"; si ya habia entrado a "Modo avanzado" a
    proposito, cambiar de proyecto no lo saca de ahi.
  - Las seis estadisticas del proyecto abierto (documentos por estado,
    trabajos en ejecucion, incidencias criticas, documentos bloqueados,
    avance por lote, ultimas actividades) solo se calculan si hay un
    proyecto abierto -- si no, la pantalla lo indica explicitamente en
    vez de mostrar datos inventados o de un proyecto distinto.
  - Con esto, las TRES piezas de la seccion 4.11 (menu funcional,
    asistente por etapas, pantalla principal) quedan completas. 568
    pruebas automatizadas en total (515 unitarias + 53 de humo,
    incluidas 5 nuevas de punta a punta sobre el dashboard), ~97.6% de
    cobertura combinada (piso: 90%), Ruff/Mypy/Bandit/pip-audit sin
    hallazgos relevantes al proyecto.
- **Mypy sobre `ui/`, Fase 11.4 (2026-07-29).** `ui` -- fuera del
  alcance de Mypy desde el inicio del prototipo, por los huecos
  conocidos de los stubs de PySide6 -- entra al `files` de
  `pyproject.toml` junto con el resto del código, sin excepción alguna
  añadida al modo estricto ya vigente. 32 errores reales encontrados en
  8 archivos, todos corregidos con el tipo correcto (no con
  `# type: ignore` salvo un único caso legítimo):
  - `QDialogButtonBox.Ok`/`.Cancel` y `QHeaderView.Stretch` (huecos
    reales de los stubs -- la forma "plana" existe en tiempo de
    ejecución pero los stubs solo reconocen la forma anidada) pasan a
    `QDialogButtonBox.StandardButton.Ok`/`.Cancel` y
    `QHeaderView.ResizeMode.Stretch`, verificado antes de cambiar el
    código que ambas formas se comportan igual en tiempo de ejecución.
  - Varios casos de angostamiento de `Optional` que Mypy no podía
    seguir (`TextoSimpleDialog.valor()`, `PantallaPrincipalWidget.
    _refrescar_resumen_proyecto()`, `_on_crear_proyecto()` en
    `etapas.py` y `proyectos_panel.py`) se resolvieron capturando el
    valor en una variable local y comprobando `is None`/`isinstance`
    sobre esa variable, en vez de sobre un booleano aparte o dos
    llamadas separadas al mismo método -- Mypy no relaciona ninguna de
    esas dos formas con el tipo real del valor.
  - `MainWindow._paginas_con_proyecto` (lista heterogénea de paneles
    que comparten el método `establecer_proyecto(pctx, proyecto)` sin
    compartir ninguna clase base propia más allá de `QWidget`) ahora se
    tipa con un `typing.Protocol` (`_PanelConProyecto`,
    `@runtime_checkable` para poder usar `isinstance` real en
    `_on_cambiar_pagina`).
  - El único `# type: ignore` real que queda es
    `ui/pdf_preview.py::render_pagina` (`QPixmap.loadFromData` con
    `str`, no `bytes` -- ver su comentario, comportamiento correcto ya
    documentado desde el Módulo 8 original).
  - El override `[[tool.mypy.overrides]] module = "ui.*", follow_imports
    = "skip"` (agregado para que `run_app.py` no arrastrara esos mismos
    huecos al importar `ui.app` dentro de `main()`) se retiró: quedó
    redundante en cuanto `ui` pasó a estar explícito en `files`
    (confirmado corriendo Mypy con y sin el override -- 0 errores en
    ambos casos).
  - Cambios de tipos únicamente, sin tocar `application`/`domain`/
    `infrastructure`: las 25 pruebas de humo de la interfaz y las 515
    pruebas unitarias siguen en verde sin cambios. Ruff, Mypy y Bandit
    limpios sobre `ui/` (dos hallazgos preexistentes de Bandit,
    `B110 try/except pass` en `ui/wizard/etapas.py`, ya documentados en
    el propio código, no relacionados con este cambio).
- **Corrección: nombres de carpeta con acentos, 2026-07-29.** Verificación
  real (no solo con pruebas automáticas de raíz temporal, sino creando y
  borrando proyectos de prueba directamente contra la carpeta real
  `proyectos/`) de que `Proyecto.carpeta_normalizada()` genera
  correctamente la carpeta física de cada proyecto nuevo. Encontrado un
  error real: un nombre de proyecto con letras acentuadas (comunes en
  español: "Área", "Configuración", "Año") producía una carpeta con
  letras perdidas en silencio (ej. "Área Legal" -> `rea_legal`, sin la
  "A"), porque la expresión regular que arma el slug no reconocía una
  letra acentuada ni como letra ni como separador. Corregido
  normalizando el nombre con Unicode NFKD antes de aplicar esa expresión
  regular, de forma que cada letra acentuada se reduzca a su letra base
  en ASCII (á/Á -> a, é/É -> e, í/Í -> i, ó/Ó -> o, ú/Ú -> u, ñ/Ñ -> n)
  en vez de desaparecer ("Área Legal" -> `area_legal`). Se agregaron dos
  pruebas nuevas (una unitaria sobre la entidad, otra de humo que crea
  la carpeta real y verifica su nombre) para que esto no vuelva a pasar
  desapercibido. Ruff, Mypy y las 516 pruebas unitarias + de humo no
  afectadas por este cambio siguen en verde.
- **Corrección: documentos atascados en "en_extraccion"/"en_normalizacion"
  tras un fallo, 2026-07-29.** Reportado por un usuario real: sin
  Tesseract instalado, la extracción de sus documentos fallaba y quedaban
  atascados en el estado `en_extraccion` para siempre -- ni siquiera un
  reintento posterior (ya con Tesseract instalado) podía recuperarlos,
  porque el flujo principal (Documento Maestro, sección 4.7) no permite
  una transición de un estado a sí mismo, y el reintento intentaba
  precisamente eso. Causa raíz: `ExtraerDocumento`/`NormalizarDocumento`
  guardan el estado intermedio (`EN_EXTRACCION`/`EN_NORMALIZACION`) antes
  de invocar al motor real, pero no tenían ningún `try/except` que
  revirtiera ese estado si el motor fallaba. Corregido en dos partes:
  - **Para fallos nuevos**: `Documento.marcar_extraccion_fallida()`/
    `marcar_normalizacion_fallida()` (nuevos métodos de dominio) revierten
    a `CLASIFICADO`/`REVISADO` respectivamente; ambos casos de uso ahora
    envuelven la llamada al motor externo en `try/except Exception` y
    llaman al método correspondiente antes de relanzar la excepción --
    el documento queda exactamente como antes del intento, listo para
    reintentarse sin intervención manual.
  - **Para documentos ya atascados** (el caso real de este usuario, con
    proyectos creados antes de esta corrección): nuevo caso de uso
    `RecuperarDocumentosInterrumpidos` (`application.documents.commands`),
    mismo principio que `RecuperarTrabajosInterrumpidos` (Fase 6) --
    revisa todos los documentos en `EN_EXTRACCION`/`EN_NORMALIZACION` al
    abrir el proyecto y los revierte automáticamente, una sola vez, antes
    de exponer el `ProjectContext` (`DocumentRepository` gana un método
    nuevo, `list_by_estado()`, mismo patrón que ya tenía
    `TrabajoRepository`). Un usuario con documentos atascados de antes de
    esta corrección solo necesita volver a abrir su proyecto -- no hace
    falta ninguna acción manual ni herramienta de reparación aparte.
  - Se agregaron pruebas de dominio (revertir y volver a fallar fuera de
    estado), de aplicación (fallo nuevo revertido en caliente, y
    recuperación retroactiva de documentos ya atascados, incluyendo un
    caso mixto `EN_EXTRACCION`+`EN_NORMALIZACION` a la vez) y contra una
    base SQLite real (no solo un repositorio falso en memoria) para
    `list_by_estado()`. Ruff, Mypy y Bandit limpios; toda la suite de
    pruebas unitarias de `application`/`domain`/`workers` y las pruebas
    de humo no gráficas relacionadas (extracción, normalización, colas de
    trabajo, cierre de lote, reportes, respaldo, pruebas de aceptación)
    en verde tras el cambio.
- **Paleta de colores de la interfaz, 2026-07-29.** A pedido del
  consultor, tras analizar si agregar color a la interfaz afecta el
  rendimiento (conclusión: no -- la app no tenía ningún
  `setStyleSheet()`/`QPalette` propio hasta ahora, solo el tema por
  defecto del sistema operativo, y no existe ningún bucle de repintado
  continuo que un color pudiera encarecer; el único costo real de
  rendimiento de esta herramienta está en el backend -- OCR,
  transcripción, LibreOffice, base de datos -- que no puede ver ni
  tocar el color de un botón, ADR-001 sección 4). Nuevo módulo
  `ui.theme`, con dos piezas:
  - **Hoja de estilos (QSS) global**, aplicada una sola vez sobre
    `QApplication` en `ui.app.main()`: identidad visual consistente
    (barra de navegación, botones, tablas, encabezados, tarjetas de la
    pantalla principal, campos de formulario) en toda la ventana, con
    la misma paleta de azules que ya usa el manual de usuario
    (`AZUL_OSCURO`/`AZUL_MEDIO`, mismos valores hexadecimales que su
    generador `build.js`) para que documento y aplicación se vean
    consistentes entre sí.
  - **Color semántico de estado**: `color_para_estado()`/
    `aplicar_color_estado()` mapean el `.value` de los cinco enums de
    estado de la aplicación (`EstadoDocumento`, `EstadoTrabajo`,
    `EstadoIncidencia`, `EstadoLote`, `EstadoProyecto` -- 34 valores en
    total, confirmados leyendo las cinco entidades reales) a cuatro
    categorías -- éxito (verde), atención (ámbar), en proceso (azul) y
    bloqueo (rojo) -- reforzando visualmente el texto de la columna
    "Estado" en las ocho tablas donde aparece (`main_window.py`,
    `procesamiento_panel.py` x2, `inventario_panel.py`,
    `normalizacion_panel.py`, `markdown_panel.py`,
    `incidencias_panel.py`, `proyectos_panel.py`) sin reemplazarlo
    nunca (el color es un refuerzo, no la única señal -- accesibilidad
    básica para variaciones de percepción del color). Los pasos
    intermedios normales del flujo (recibido, clasificado, extraído...)
    se dejan sin color especial a propósito, para que las filas que sí
    necesitan destacar resalten por contraste.
  - Ruff, Mypy (209 archivos) y Bandit limpios (mismos dos hallazgos
    preexistentes de Bandit en `ui/wizard/etapas.py`, ya documentados,
    no relacionados con este cambio). Esta sesión de trabajo no tiene
    acceso a las librerías gráficas del sistema (`libEGL`), así que no
    se pudo tomar una captura de pantalla ni correr las pruebas de humo
    de la interfaz para verificación visual directa -- se recomienda
    que el usuario confirme el resultado visual la próxima vez que abra
    la aplicación en su propio equipo.
- **Corrección: ruta raíz hardcodeada a Linux, 2026-07-30.** Reportado
  por un usuario probando la herramienta en Windows: creó un proyecto
  nuevo y terminó guardado en una ruta inesperada. Causa raíz:
  `app.configuration` tenía hardcodeada la ruta raíz por defecto de
  TODA la aplicación como una cadena de Linux literal
  (`/media/disco/Data/RAG CONTENT STUDIO`, el disco del consultor) --
  en Windows esa misma cadena se interpreta como una ruta relativa a la
  unidad de trabajo actual, no como la ruta Linux original, dejando el
  proyecto en un lugar no obvio para el usuario. Este riesgo ya estaba
  señalado en ADR-001, sección 11, como pendiente de resolver "antes de
  probar en Windows/macOS" -- nunca se había parametrizado hasta que un
  usuario real lo encontró.
  - Corregido: `app.configuration.cargar_rutas()` ahora resuelve la
    raíz en tres pasos, en orden -- argumento explícito (solo pruebas),
    variable de entorno `RAG_CONTENT_STUDIO_ROOT` (para que una
    instalación existente, incluida la del propio consultor, conserve
    su carpeta actual sin mover nada), o si ninguna aplica, una carpeta
    dentro del home del usuario (`Path.home()`) calculada en tiempo de
    ejecución con `pathlib` -- nunca una cadena fija en el código,
    igual en Windows, macOS y Linux.
  - Se agregaron pruebas unitarias nuevas para `app.configuration`
    (no existían antes de este cambio) cubriendo las tres prioridades
    de resolución.
  - Se actualizaron las secciones 4.1 y 4.5 del Documento Maestro (la
    ruta raíz ya no se declara como una cadena fija) y la sección 11
    del ADR-001 (el riesgo correspondiente se marca como mitigado), más
    una nueva sección 1 en `MANUAL_OPERACION.md` con instrucciones
    exactas para fijar la variable de entorno en Windows (PowerShell) y
    macOS/Linux (perfil de la shell).
  - Ruff, Mypy (209 archivos) y Bandit limpios; toda la suite de
    pruebas unitarias de `application`/`domain`/`workers` y las pruebas
    de humo no gráficas relacionadas con la creación de proyectos en
    verde tras el cambio.
- **Corrección: la pestaña "Revisión" no se refrescaba al navegar hacia
  ella, 2026-07-30.** A pedido del consultor: validar que en "Revisión"
  se puedan ver listados los archivos ya procesados, reflejados de
  verdad, para poder cotejarlos contra su original. Encontrado un bug
  real al leer el código junto con las propias pruebas de humo
  existentes: `tabla_documentos` de "Revisión" solo se cargaba al abrir
  el proyecto (`_on_abrir_proyecto()`) o al aprobar una revisión
  (`_on_aprobar_revision()`) -- a diferencia de los otros once paneles
  del menú (Inventario, Procesamiento, Normalización...), que
  implementan `establecer_proyecto()` y por eso se refrescan solos cada
  vez que `_on_cambiar_pagina()` detecta un cambio de pestaña,
  "Revisión" es la pantalla original del prototipo (anterior a la Fase
  11) y quedó fuera de ese mecanismo. Un documento clasificado/extraído
  en "Procesamiento" (u otra pestaña) mientras el operador ya tenía el
  proyecto abierto no aparecía reflejado en "Revisión" hasta cerrar y
  volver a abrir el proyecto -- justamente lo contrario de lo que esta
  pantalla existe para permitir. Prueba de que el bug era real y ya
  conocido de forma implícita: las pruebas de humo existentes
  (`test_gui_revision_incidencias_extremo_a_extremo.py`,
  `test_gui_menu_completo_extremo_a_extremo.py`) ya tenían que forzar
  un `ventana._cargar_documentos()` manual, en cinco lugares distintos,
  para poder seleccionar una fila después de navegar a esa pestaña --
  sin ese parche manual, la tabla habría seguido mostrando 0 filas.
  - Corregido: `_on_cambiar_pagina()` ahora también refresca
    `tabla_documentos` al entrar a "Revisión" (guardada como
    `self.pagina_revision`), con el mismo criterio de baja fricción que
    el resto de los paneles (Documento Maestro, sección 4.11.1):
    `_cargar_documentos()` preserva la fila seleccionada a través del
    recargue, en vez de perder la selección cada vez que el operador
    vuelve a esta pestaña.
  - Se quitaron las cinco llamadas manuales a `_cargar_documentos()`
    que las pruebas de humo ya usaban como parche, reemplazándolas por
    una navegación real de pestaña (`_ir_a_revision()`, nuevo helper
    compartido) que ahora prueba el refresco automático de punta a
    punta, en vez de esconder el bug llamando directo al método
    interno.
  - Ruff, Mypy (209 archivos) y Bandit limpios. Esta sesión de trabajo
    no tiene acceso a las librerías gráficas del sistema (`libEGL`),
    así que no se pudieron ejecutar las propias pruebas de humo de la
    interfaz para confirmarlo en verde de punta a punta (mismo límite ya
    documentado en la entrada de la paleta de colores) -- se recomienda
    correrlas en un equipo con entorno gráfico real
    (`pytest tests/smoke/test_gui_revision_incidencias_extremo_a_extremo.py
    tests/smoke/test_gui_menu_completo_extremo_a_extremo.py`) antes de
    dar este cambio por cerrado.
- **Mensajes de error accionables ante `PermissionError` en Windows,
  2026-07-30.** Reportado por el usuario de Windows: al generar los seis
  informes desde "Reportes", la aplicación mostraba el texto crudo de
  Python (`[Errno 13] Permission denied: 'C:\Usuarios\aleja\RAG Content
  Studio Desktop\proyectos\PROY-0519...\10_reportes\informe_
  inventario.csv'`), y varias otras acciones fallaban igual sin decirle
  al usuario qué hacer. Se verificó el código de escritura
  (`infrastructure/filesystem/local_report_writer.py` y equivalentes):
  cada escritor abre el archivo en modo escritura con `with ... open(...)`
  (cierre garantizado, sin handles filtrados) y no hay doble escritura ni
  doble conexión de señales -- el propio código Python nunca deja un
  archivo abierto ni lo lee de vuelta (la función "abrir archivo" del
  listado de reportes solo delega a `QDesktopServices.openUrl()`, sin
  tocar el archivo desde Python). Es decir, no es un bug de escritura
  duplicada: el `PermissionError` viene de fuera del proceso Python --
  casi siempre el archivo abierto en otro programa (Excel) o con el
  atributo de solo lectura activado, algo mucho más común en Windows que
  en Linux.
  - Corregido: nuevo módulo `ui/errores.py` con
    `mensaje_amigable(exc)`, que detecta específicamente
    `PermissionError` y devuelve una explicación en español de las dos
    causas más probables (archivo abierto en otro programa, o atributo
    de solo lectura) y qué hacer en cada caso, incluyendo el nombre del
    archivo afectado; para cualquier otra excepción se comporta igual
    que el `str(exc)` que se mostraba antes.
  - Aplicado en los 12 archivos de `ui/` (`main_window.py` y los paneles
    de Procesamiento, Incidencias, Normalización, Configuración,
    Inventario, Markdown, Reportes, Proyectos, Pruebas, más el asistente
    por etapas y la pantalla principal) donde se le muestra al usuario el
    texto de una excepción no controlada.
  - `ui/errores.py` no importa PySide6 (es una función pura), así que a
    diferencia del resto de `ui/` sí se pudo cubrir con pruebas unitarias
    reales en este entorno de trabajo (`tests/unit/ui/test_errores.py`,
    4 casos, incluido uno que reproduce el `PermissionError` exacto del
    reporte de Windows) -- todas en verde.
  - Ruff, Mypy (210 archivos) y Bandit limpios (mismos 2 hallazgos Low
    preexistentes en `ui/wizard/etapas.py`, ya documentados, no
    relacionados con este cambio).
- **La carpeta raíz de datos ahora es visible desde la propia interfaz,
  2026-07-30.** Comentario adicional del mismo usuario de Windows:
  "sigue sin mostrar los archivos del proyecto en la carpeta de
  proyectos" -- al aclarar con el consultor, resultó ser que al crear un
  proyecto nuevo no se estaba guardando donde el usuario esperaba
  (donde tiene instalada la herramienta), sino en otra ruta. Investigado
  el código: hay un único punto de resolución de la raíz
  (`app.bootstrap.bootstrap()` llama a `cargar_rutas()` una sola vez) y
  un único punto de creación de proyectos (`LocalProjectFileStore` sobre
  `rutas.proyectos`), así que no hay una ruta alterna hardcodeada en
  ningún lado -- pero ninguna pantalla de la interfaz mostraba nunca cuál
  era esa carpeta resuelta. Sin eso, un usuario no tiene forma de saber
  dónde está buscando exactamente, y en un equipo con más de un usuario o
  perfil de Windows (la variable de entorno `RAG_CONTENT_STUDIO_ROOT` o
  el usuario de Windows activo pueden cambiar cuál carpeta resulta de
  `Path.home()`) es fácil terminar buscando en el lugar equivocado --
  coherente con las varias carpetas de proyectos dispersas que aparecen
  en la captura de Explorador que envió el usuario.
  - Corregido: la pantalla "Configuración" ahora muestra la carpeta raíz
    de datos resuelta en tiempo real (texto seleccionable, para poder
    copiarla) y un botón "Abrir carpeta de proyectos" que la abre directo
    en el explorador de archivos del sistema operativo -- el usuario ya
    no tiene que adivinar ni buscarla a mano.
  - Se recomienda al consultor confirmar con el usuario de Windows si su
    equipo tiene más de un usuario/perfil de Windows, o si alguna vez se
    fijó `RAG_CONTENT_STUDIO_ROOT` con un valor distinto en ese equipo --
    ambas cosas explicarían por qué proyectos nuevos terminaron en rutas
    distintas a través de sesiones distintas (ver sección 1 de
    `MANUAL_OPERACION.md` para fijar la variable de forma permanente y
    evitar que vuelva a pasar).
  - Ruff, Mypy (210 archivos) y Bandit limpios.
- **"Pruebas de aceptación" ahora muestra por qué falla cada dominio,
  2026-07-31.** El consultor reportó un caso real desde su propio
  equipo: al correr "Ejecutar pruebas" contra una carpeta de prueba
  (`/media/disco/Data/temporal`), la pantalla mostró "Inventario: FALLA"
  y los otros seis dominios como "PENDIENTE", sin ninguna forma de saber
  por qué desde la propia interfaz -- solo abriendo a mano el informe
  Markdown en `10_reportes/` se podía leer el detalle. Validado contra
  el código y las pruebas unitarias existentes
  (`test_un_archivo_que_falla_no_aborta_la_corrida_completa`): ese
  patrón exacto ("Inventario: FALLA" + el resto "PENDIENTE") es
  consistente y significa que TODOS los archivos de esa carpeta
  fallaron durante el procesamiento (si al menos uno se hubiera
  procesado con éxito, los demás dominios mostrarían CUMPLE/FALLA real,
  no PENDIENTE) -- no es un bug de las pruebas de aceptación, es el
  resultado correcto para un corpus donde ningún archivo se pudo
  procesar; la razón específica de cada archivo ya vivía en
  `criterio.detalle` desde la Fase 9, solo que la pantalla nunca la
  mostraba.
  - Corregido: `PruebasPanel` ahora muestra el detalle de cada dominio
    junto a su marca (CUMPLE/FALLA/PENDIENTE), recortado si es muy
    largo, con el texto completo disponible como tooltip al pasar el
    mouse -- ya no hace falta salir de la aplicación para saber qué
    pasó.
  - Ruff, Mypy (210 archivos) y Bandit limpios; pruebas unitarias no
    gráficas relacionadas en verde.
- **Aclarado el propósito real de "Ejecutar pruebas" dentro del
  asistente guiado, 2026-07-31.** Con el informe compartido por el
  consultor (ver entrada anterior) se confirmó la causa exacta de la
  siguiente FALLA: el corpus tenía un solo archivo, y ya existía en ese
  mismo proyecto otro documento registrado con el mismo hash SHA-256
  (mismo contenido) -- el Módulo 3 (detección de duplicados) lo bloqueó
  correctamente. El usuario reportó el mismo resultado una segunda vez
  al apuntar a una copia exacta del archivo en otra carpeta, y explicó
  que no le quedaba claro qué hace este paso dentro del asistente: lo
  sigue como parte del procesamiento normal de su documento, entre
  "Generar Markdown" y "Cerrar lote". Causa raíz real (no del código,
  de la experiencia de uso): `PruebasPanel` se reutiliza tal cual como
  "Etapa 9 de 10" del asistente, pero `AcceptanceService` (Fase 9) SIEMPRE
  vuelve a registrar desde cero cualquier archivo de la carpeta de
  corpus que se le indique, de forma independiente del documento que el
  usuario ya procesó en las etapas anteriores -- es una revisión de
  control de calidad de la herramienta misma contra documentos
  representativos (sección 8.1/8.2), no una validación del documento en
  turno. Apuntarla a una copia del mismo archivo ya registrado en el
  proyecto siempre topará con la detección de duplicados, sin importar
  la carpeta o el nombre del archivo.
  - Corregido: la pantalla ahora explica esto en texto plano, en el
    mismo lugar donde el usuario la ve (tanto en el menú completo como
    dentro del asistente, que reutiliza el mismo panel): que no evalúa
    el documento recién procesado, que vuelve a registrar desde cero
    cualquier archivo del corpus indicado, que un archivo ya registrado
    en este proyecto producirá una falla esperada de duplicados (no un
    error de la herramienta), y que el paso es opcional -- se puede
    pasar directo a "Cerrar lote" sin ejecutarlo.
  - Ruff, Mypy (210 archivos) y Bandit limpios.
- **Mejor distribución del espacio en la pantalla "Revisión", 2026-07-31.**
  El consultor compartió una captura señalando que la distribución no
  aprovechaba bien el espacio: la tabla "Documentos del proyecto"
  truncaba el encabezado "Tipo de procesamiento" a "de procesam", y el
  panel lateral (incidencias, fechas/cifras detectadas, vigencia y
  fuente) apretaba varias secciones sin ninguna forma de desplazarse si
  no cabían en la ventana. Causa raíz: la tabla usaba el modo de ajuste
  "Interactive" de Qt con anchos fijos pequeños por defecto, sin
  relación con el ancho real disponible del panel; y el panel lateral no
  estaba envuelto en ningún `QScrollArea`, así que su contenido podía
  quedar recortado en vez de desplazarse.
  - Corregido: la tabla de documentos ahora usa el modo "Stretch" (usa
    todo el ancho disponible del panel, repartido entre las tres
    columnas); el panel lateral ahora vive dentro de un `QScrollArea`
    (nada queda recortado sin importar el tamaño de la ventana); las
    listas de incidencias y de fechas/cifras tienen una altura mínima y
    factor de estiramiento explícitos para repartir mejor el espacio
    vertical disponible; y las proporciones iniciales de los splitters
    se reajustaron para darle más espacio al área de trabajo real (el
    visor Original/Normalizado) y al panel lateral, y menos a la lista
    de documentos (que normalmente solo necesita mostrar tres columnas
    cortas) -- el usuario sigue pudiendo mover los splitters a mano,
    esto solo mejora el punto de partida.
  - Ruff, Mypy (210 archivos) y Bandit limpios.
- **Barra de progreso en la etapa "Procesar" del asistente, 2026-07-31.**
  El consultor pidió, para esta etapa, una barra de porcentaje y saber
  qué archivo se está procesando (con su ruta), para que el usuario sepa
  que la herramienta sigue trabajando y pueda ver el avance. Causa del
  problema: `EtapaProcesar._on_procesar()` clasifica y extrae cada
  documento pendiente en un ciclo síncrono sobre el hilo de la interfaz,
  sin ninguna señal visual mientras corre -- clasificar/extraer puede
  tardar bastante por documento (OCR, transcripción de audio/video,
  conversión de formatos legados), y sin retroalimentación el usuario no
  tiene forma de distinguir "sigue trabajando" de "se colgó". No existe
  todavía ningún mecanismo real de segundo plano en la herramienta (ni
  siquiera la "cola de trabajos" de Fase 6 lo es: también procesa de
  forma síncrona bajo demanda, ver `ui/panels/procesamiento_panel.py`),
  así que introducir hilos reales habría sido un cambio arquitectónico
  mucho más grande y riesgoso (la sesión de base de datos de SQLAlchemy
  se comparte, no es segura entre hilos) para lo que se pedía.
  - Corregido con un `QProgressDialog` (patrón estándar de Qt para
    operaciones síncronas largas, sin necesitar hilos): muestra el
    porcentaje de avance y, para cada documento, su nombre y la ruta de
    su copia original mientras se procesa, actualizado entre cada
    documento con `processEvents()` para que se repinte en tiempo real;
    el usuario también puede cancelar a mitad de camino -- los
    documentos ya procesados quedan como tal, los restantes siguen
    pendientes para la próxima corrida.
  - Alcance: solo la etapa "Procesar" del asistente, que es la que se
    pidió y la que más tarda por documento. Las demás etapas con el
    mismo patrón de ciclo síncrono (Normalizar, Aprobar, Generar
    Markdown) no se tocaron -- son operaciones mucho más rápidas por
    documento y no fueron parte de este pedido; se puede aplicar el
    mismo patrón ahí si en el futuro hace falta.
  - Ruff, Mypy (210 archivos) y Bandit limpios.
- **Reconstrucción de tablas escaneadas por OCR, 2026-07-31.** El
  consultor compartió una captura donde un plan de estudios escaneado
  (materias agrupadas en columnas por cuatrimestre) perdía esa
  estructura al normalizarse: las materias de las tres columnas
  quedaban concatenadas en el mismo renglón, sin indicar a cuál
  cuatrimestre pertenecía cada una. Causa raíz confirmada: la ruta OCR
  (`TesseractOcrEngine`) solo llamaba a `pytesseract.image_to_string()`,
  que devuelve el texto de la página completa como un bloque plano, sin
  ninguna noción de columnas -- a diferencia de los extractores de
  formatos con estructura tabular nativa (CSV/XLSX/DOCX), que sí la
  conservan. Se presentaron tres opciones (heurística propia sin
  dependencias nuevas, librería especializada de detección de tablas
  con OpenCV, o no automatizarlo por ahora); el consultor eligió la
  heurística propia.
  - Corregido: nuevo módulo puro `domain.documents.
    ocr_table_reconstruction` (sin pytesseract, ADR-001 sección 4). Se
    cambió `TesseractOcrEngine` para usar `pytesseract.image_to_data()`
    en vez de `image_to_string()` (mismo binario, mismos fallos
    posibles) -- da la posición de cada palabra reconocida, que la
    nueva función agrupa en columnas (según el tamaño del hueco
    horizontal entre palabras, proporcional a la altura de línea, no a
    un pixelaje fijo) y filas (líneas consecutivas con el mismo número
    de columnas). Un grupo de al menos 3 líneas con 2 o más columnas se
    emite como tabla Markdown real (`| ... |`), que el Módulo 9 ya sabe
    limpiar (`normalizar_espacios_en_tablas`) igual que una tabla
    nativa. El resto del texto (la mayoría de los documentos OCR, que
    no son tablas) se reconstruye igual que antes, con líneas en blanco
    entre párrafos.
  - Es una heurística, no detección perfecta -- documentado a propósito
    en el módulo: tablas con celdas vacías en algunas filas, o sin un
    hueco horizontal claro entre columnas, no se detectan como tabla y
    quedan como texto plano (igual que antes de este cambio, nunca
    peor).
  - Verificado de punta a punta contra el binario real de Tesseract
    instalado en este entorno (no solo con datos sintéticos): una
    imagen de tabla de 3 columnas x 4 filas se reconstruye como tabla
    Markdown correcta, y un párrafo normal de prueba NO se confunde con
    una tabla -- ambos casos cubiertos con pruebas nuevas
    (`tests/unit/domain/test_ocr_table_reconstruction.py`, función pura;
    `tests/unit/application/test_tesseract_ocr_engine.py`, con Tesseract
    real). Las 6 pruebas unitarias existentes de `TesseractOcrEngine`
    (que no se tocaron) y las de `ImageOcrExtractor`/`PdfOcrExtractor`
    siguen en verde sin cambios.
  - Ruff, Mypy (211 archivos) y Bandit limpios.
- **Auditoría de una corrida real completa (PROY-5288_udl) y mejora de
  los informes de calidad/procesamiento, 2026-07-31.** El consultor
  pidió analizar los archivos de un proyecto ya procesado de punta a
  punta para encontrar detalles a corregir/depurar/mejorar. Hallazgos
  confirmados:
  - **Impacto real y medible del fix de tablas OCR de este mismo día**:
    el `07_markdown` de esa corrida (procesada ANTES del fix) no tenía
    ningún encabezado ni tabla real -- `informe_calidad.csv` ya lo tenía
    registrado como advertencia, y `domain.documents.
    estructura_markdown.tiene_estructura_markdown()` confirma que
    hubiera sido tratado por RAG STUDIO como un solo bloque sin fragmentar.
    Se volvió a extraer el mismo PDF original con el código ya corregido
    y se confirmó que ahora sí produce tablas Markdown reales y
    `tiene_estructura_markdown()` da `True` -- evidencia directa de que
    el fix de esa mañana resuelve un problema real, no solo cosmético.
  - **`informe_calidad.csv`/`informe_procesamiento.csv` solo mostraban
    la CANTIDAD de advertencias, nunca el texto** -- confirmado con el
    caso real de arriba: el CSV decía "advertencias_markdown: 1" sin
    ninguna forma de saber, desde el propio informe, cuál era esa
    advertencia. Corregido: `FilaCalidad.advertencias_extraccion`/
    `advertencias_markdown` y `FilaProcesamiento.advertencias` ahora
    llevan el texto completo de cada advertencia (unidas con '; ' igual
    que ya se hacía con `incumplimientos`), no solo un conteo.
  - Verificado y descartado como error, tras revisar el contrato
    confirmado con RAG STUDIO (Documento Maestro, sección 4.6.1): la
    columna `autoridad_fuente` del manifiesto vacía NO es un bug --
    corresponde a `source_authority` (un número entero de prioridad,
    "vacío si no se prioriza"), no al campo `Fuente.autoridad` (texto
    libre); esta versión no tiene ningún mecanismo para asignar esa
    prioridad numérica todavía, así que dejarla vacía es exactamente lo
    especificado.
  - Verificado y descartado como error: `semaforo='verde'` con
    advertencias presentes -- diseño intencional documentado en
    `_calcular_semaforo()` (el semáforo refleja si el documento cumple
    la gobernanza de liberación, no si está libre de cualquier
    advertencia).
  - Observación sin cambio de código (limitación conocida de OCR, no
    accionable de forma segura en este momento): números romanos
    confundidos con dígitos ("III" -> "111", "II" -> "11") y texto de
    encabezados con fondo de color mal reconocido -- confirmado, con una
    comparación directa `image_to_string()` vs `image_to_data()` sobre
    la misma imagen, que esto ocurre EN AMBOS casos por igual (no lo
    introdujo el fix de tablas): es una limitación de precisión de
    Tesseract sobre texto estilizado, no de la logica de reconstruccion.
  - Ruff, Mypy (211 archivos) y Bandit limpios; pruebas relacionadas de
    `application`/`domain` en verde.
- **Dialogo de progreso en negro ("no responde") durante "Procesar",
  2026-07-31.** El consultor compartió dos capturas: una del asistente
  en la etapa "Procesar", con el `QProgressDialog` agregado esa misma
  mañana (ver arriba) completamente en negro y los botones nativos de
  Windows "Forzar la salida"/"Esperar" -- el aviso de que la aplicación
  "no responde" --; y otra de "Revisión" (modo avanzado, proyecto
  UDL2/PROY-4430) mostrando el resultado del fix de tablas OCR de esa
  misma mañana ya funcionando en una máquina real con Windows.
  - **Causa real del diálogo en negro**: el primer intento del
    `QProgressDialog` solo llamaba `QApplication.processEvents()` UNA
    vez por documento, antes de clasificar/extraer -- con un solo
    documento pendiente (como en la captura, "1 documento(s)
    pendiente(s)") o un documento con muchas páginas de OCR, esa única
    llamada no bastaba: el hilo de la interfaz quedaba bloqueado el
    resto del tiempo dentro de `extraer_documento()`, tiempo más que
    suficiente para que Windows considere la ventana congelada -- el
    diálogo recién creado ni siquiera alcanzaba a pintarse una primera
    vez, de ahí el negro. Se descartó de nuevo un hilo real (`QThread`):
    `infrastructure/database/engine.py` abre SQLite con las opciones por
    defecto de SQLAlchemy, sin `check_same_thread=False`, así que mover
    estas llamadas a otro hilo fallaría de inmediato, no solo sería
    "arriesgado".
  - Corregido con un callback opcional `on_progreso(pagina_actual,
    total_paginas)` agregado a `DocumentExtractor.extract()`
    (`domain/documents/ports.py`), reenviado sin tocar por
    `CompositeDocumentExtractor`, `ExtraerDocumento.execute()` y
    `DocumentsService.extraer_documento()`. Solo `PdfOcrExtractor` lo
    invoca de verdad (único tramo genuinamente lento página por página
    en este contexto); los demás extractores lo reciben y lo ignoran
    sin romper su contrato. `EtapaProcesar._on_procesar()` ahora llama
    `processEvents()` una vez POR PÁGINA de OCR, no solo una vez por
    documento -- sigue siendo síncrono de punta a punta, sin ningún hilo
    nuevo, solo con más puntos donde la interfaz tiene oportunidad de
    repintarse.
  - Segunda captura (Revisión, UDL2/PROY-4430): confirmada como evidencia
    real, en una máquina Windows del usuario final, de que el fix de
    reconstrucción de tablas OCR de esa misma mañana funciona
    correctamente -- el panel "Extraído/revisado" muestra tablas
    Markdown reales (encabezado, fila separadora y filas de datos) para
    el contenido de cuatrimestres, en vez del texto plano sin estructura
    de antes. No se encontraron mejoras adicionales pendientes en esa
    captura.
  - Pruebas nuevas: `test_pdf_ocr_extractor_invoca_on_progreso_una_vez_por_pagina`
    (`tests/unit/application/test_ocr_extractors.py`) y
    `test_extraer_documento_reenvia_on_progreso_al_extractor`
    (`tests/unit/application/test_documents_service.py`). Se actualizaron
    también los dobles de prueba de `DocumentExtractor` en
    `test_documents_service.py` y `test_normalizar_documento.py` para
    aceptar el nuevo parámetro opcional (nunca rompe compatibilidad hacia
    atrás: los 4 llamadores existentes de `extraer_documento()` siguen
    funcionando sin cambios).
  - Ruff, Mypy (211 archivos) y Bandit limpios; 364 pruebas de
    `tests/unit/application` más las de `tests/unit/domain`, `tests/unit/app`
    y `tests/unit/workers` en verde.
- **Auditoría de PROY-6955_udl_3 y filas de tabla incompletas tras OCR,
  2026-07-31.** El consultor pidió auditar otra corrida real completa
  (mismo documento de plan de estudios que PROY-5288_udl, ya
  reprocesado con el fix de tablas OCR de esa misma mañana). Confirmado
  en el propio `07_markdown`, en una máquina real con Windows y el
  paquete de idioma español instalado: las 6 tablas del documento se
  reconstruyen como tablas Markdown reales, con acentos correctos --
  evidencia adicional de que el fix funciona en producción.
  - **Hallazgo nuevo**: en 4 de las 6 tablas, la ÚLTIMA fila queda fuera
    de la tabla, como líneas de texto sueltas sin indicar a qué
    cuatrimestre pertenecen (por ejemplo "Metodología de la
    Investigación" / "Economía" / "Autoconocimiento" aparecen como 3
    líneas sueltas después de la primera tabla). Causa confirmada
    reproduciendo el mismo PDF con `pytesseract.image_to_data()` real en
    este entorno: **no es un error de la heurística** -- es Tesseract
    mismo quien separa esa fila en varias líneas/bloques distintos (una
    por columna) antes de que `domain.documents.
    ocr_table_reconstruction` vea los datos. Ningún ajuste de umbral
    puede reunirlas de vuelta sin reconstruir filas a partir de la
    posición Y cruda de cada palabra (la solución más robusta, con una
    librería especializada, que se descartó explícitamente el mismo día
    en que se eligió esta heurística propia).
  - `informe_calidad.csv` no señalaba nada de esto
    (`semaforo='verde'`, `advertencias_markdown` vacío) -- el problema
    pasaba inadvertido salvo revisión manual línea por línea.
  - Corregido **sin alterar el texto de salida** (para no arriesgar
    asignar mal una materia al cuatrimestre equivocado):
    `reconstruir_texto_ocr()` ahora devuelve también una lista de
    advertencias, detectando cuando 1 o más líneas cortas justo después
    de una tabla detectada podrían ser una fila incompleta -- acotado a
    lo sumo al número de columnas de la tabla, y a líneas de pocas
    palabras, para no confundir un párrafo normal con un fragmento de
    celda. Esa advertencia se propaga hasta
    `ResultadoExtraccion.advertencias` a través de un cambio de contrato
    en el puerto `domain.documents.ports.OcrEngine.image_to_text()`
    (ahora devuelve `(texto, advertencias)`), implementado en
    `TesseractOcrEngine` y consumido por `PdfOcrExtractor`/
    `ImageOcrExtractor` -- única implementación real de `OcrEngine` en
    el proyecto.
  - Pruebas nuevas:
    `test_fila_incompleta_justo_despues_de_una_tabla_se_senala_como_advertencia`
    y `test_parrafo_normal_despues_de_tabla_no_se_marca_como_fila_incompleta`
    (`tests/unit/domain/test_ocr_table_reconstruction.py`).
  - Ruff, Mypy (211 archivos) y Bandit limpios; 542+ pruebas de
    `application`/`domain`/`app`/`workers` en verde.
- **Carpeta consolidada de entrega para RAG Studio, 2026-07-31.** El
  consultor pidió que, al terminar de procesar los documentos que se
  deben entregar a RAG STUDIO, la herramienta los deje listos en un solo
  directorio (sugerencia: "14_RAG Studio"), para que el operador no
  tenga que ir a buscar archivos en carpetas distintas. Implementado
  como `14_entrega_rag_studio/` (nombre ajustado a la convención de las
  otras 13 subcarpetas -- sin espacios, snake_case, con prefijo
  numérico).
  - Nuevo puerto `domain.documents.ports.EntregaRagStudioStore.
    preparar(ruta_manifiesto, rutas_markdown) -> str`, implementado en
    `infrastructure/filesystem/entrega_rag_studio_store.py`
    (`LocalEntregaRagStudioStore`): recrea la carpeta desde cero en cada
    corrida (determinista, mismo criterio que `ManifestWriter` -- nunca
    acumula copias de documentos que ya no están LIBERADO) y copia el
    manifiesto más cada Markdown liberado.
  - Nuevo caso de uso `PrepararEntregaRagStudio`
    (`application/documents/commands/preparar_entrega_rag_studio.py`),
    que **reusa** `GenerarManifiesto` sin duplicar su lógica de armado
    de filas ni cambiar el manifiesto canónico de `12_exportaciones/`
    (que sigue siendo la única fuente de verdad, Documento Maestro
    sección 4.6.1) -- `14_entrega_rag_studio/` es una copia adicional,
    puramente de conveniencia.
  - Conectado en dos puntos: el botón de la pantalla Markdown (modo
    avanzado), renombrado a "Preparar entrega para RAG Studio", ahora
    llama a este caso de uso en vez de solo generar el manifiesto; y la
    etapa "Cerrar lote" del asistente lo invoca automáticamente justo
    después de cerrar el lote (el momento natural de "ya terminé de
    procesar estos archivos"), de forma no bloqueante -- si falla, el
    lote ya quedó cerrado igual, solo se avisa en pantalla.
  - Documento Maestro actualizado: sección 4.5 (árbol de carpetas, 14ª
    subcarpeta) y sección 4.6.1 ("Entrega y granularidad", nota sobre la
    carpeta consolidada). No se tocó ADR-001 sección 8 (tabla de
    puertos): esa tabla ya no se mantenía al día con puertos más
    recientes como `ManifestWriter`, mismo criterio de alcance.
  - Pruebas nuevas: `tests/unit/application/
    test_entrega_rag_studio_store.py` y `test_preparar_entrega_rag_studio.py`.
  - Ruff, Mypy (213 archivos) y Bandit limpios; 550+ pruebas de
    `application`/`domain`/`app`/`workers` más los smoke tests relevantes
    (crear proyecto, cerrar lote, generar Markdown) en verde.
- **Paneles laterales plegables en "Revisión", 2026-07-31.** El
  consultor compartió dos capturas de la pantalla "Revisión" (modo
  avanzado) y pidió que los paneles laterales -- "Documentos del
  proyecto" (izquierdo) y "Estado" (derecho: estado del documento,
  incidencias, fechas/cifras detectadas, vigencia y fuente) -- se
  pudieran plegar y desplegar con botones, para aprovechar mejor el
  visor central (Original/Normalizado) cuando el operador ya eligió el
  documento y solo quiere comparar texto.
  - Implementado en `MainWindow._construir_pagina_revision()`: dos
    `QPushButton` "checkable" (interruptores) arriba del splitter
    principal -- "Ocultar documentos"/"Mostrar documentos" y "Ocultar
    estado"/"Mostrar estado", el texto cambia según el estado actual --
    que ocultan/muestran el widget correspondiente dentro del
    `QSplitter`; Qt ya redistribuye automáticamente el espacio de un
    widget oculto entre los demás hijos del splitter, sin lógica
    adicional de recálculo de tamaños.
  - Estado por defecto: ambos paneles visibles, igual que antes de este
    cambio -- el operador activa el plegado solo cuando lo necesita.
  - Prueba nueva:
    `test_paneles_de_documentos_y_estado_se_pueden_ocultar_y_mostrar`
    (`tests/smoke/test_gui_revision_incidencias_extremo_a_extremo.py`).
  - Ruff, Mypy (213 archivos) y Bandit limpios.
- **"Ejecutar pruebas" deja de ser una etapa del asistente; aviso de
  cierre de lote reforzado con ventana emergente, 2026-07-31.** El
  consultor propuso tres cambios, considerando que la herramienta ya
  maduró:
  1. Que la etapa "Ejecutar pruebas" no aparezca en el modo Asistente,
     dejándola como funcionalidad exclusiva del Modo Avanzado.
     - Analizado y confirmado: `PruebasPanel` (Fase 9) es una
       herramienta de QA que valida el motor de extracción/OCR en
       general contra un corpus ad-hoc propio (no del proyecto que se
       está trabajando) -- no es un paso del flujo lineal por proyecto,
       y ya estaba disponible de forma independiente en Modo Avanzado
       ("Pruebas de aceptación" en el menú). Se quitó de
       `AsistenteWidget` (`ui/wizard/asistente_widget.py`): el asistente
       pasa de diez a **nueve** etapas ("Etapa 1 de 9" en vez de "Etapa
       1 de 10"). No se tocó `PruebasPanel` ni su acceso en Modo
       Avanzado.
  2. Analizar si es pertinente crear un nuevo módulo de "Configuración
     avanzada" en Modo Avanzado, para exponer los aspectos que describe
     `MANUAL_OPERACION.md`.
     - **Conclusión: no está justificado por ahora.** La mayor parte de
       lo que describe el manual ya tiene pantalla propia en
       `ConfiguracionPanel` (ruta raíz de proyectos, creación de
       perfiles, respaldo/restauración cifrados). Lo que falta exponer
       en UI (variable de entorno `RAG_CONTENT_STUDIO_ROOT`, la clave de
       cifrado) es así **a propósito**: son decisiones de seguridad/
       arranque que no deben quedar editables ni visibles desde dentro
       de la aplicación. El único hueco real -- las reglas de
       normalización/validación de un perfil, que `CrearPerfilDialog`
       deja explícitamente en YAML fuera de la ventana -- no amerita un
       módulo nuevo completo; si en el futuro se decide exponerlo, basta
       con ampliar el `ConfiguracionPanel` existente. De paso quedó
       identificado (no corregido, es documentación) que la sección 6
       de `MANUAL_OPERACION.md` describe la restauración de respaldos
       como si no tuviera pantalla propia, cuando `ConfiguracionPanel`
       ya la tiene -- una actualización menor pendiente del manual, sin
       impacto en código.
  3. Validar si el botón "Crear lote con todos los documentos y
     cerrarlo" avisa con una ventana de mensaje que los archivos ya
     están listos para RAG Studio en `14_entrega_rag_studio/`.
     - **Validado: no lo hacía.** `EtapaCerrarLote._on_cerrar_lote()`
       solo actualizaba una etiqueta de texto en pantalla (fácil de
       pasar por alto), sin ningún `QMessageBox`, a diferencia de las
       demás etapas del asistente (Procesar, Normalizar, Aprobar,
       Generar Markdown), que sí muestran una ventana emergente con el
       resultado del lote. Corregido agregando `QMessageBox.information`
       (cierre exitoso) o `QMessageBox.warning` (lote cerrado pero la
       entrega hacia RAG Studio falló, por ejemplo por permisos) con el
       mismo mensaje que ya se mostraba en la etiqueta -- que se
       conserva sin cambios.
  - Pruebas actualizadas:
    `tests/smoke/test_asistente_por_etapas_extremo_a_extremo.py` (nueve
    etapas en vez de diez, se quitó el bloque de "Etapa 9: ejecutar
    pruebas" y se ajustaron los conteos de documentos/liberados que
    dependían de él).
  - Ruff, Mypy y Bandit limpios en los archivos tocados
    (`ui/wizard/etapas.py`, `ui/wizard/asistente_widget.py`,
    `tests/smoke/test_asistente_por_etapas_extremo_a_extremo.py`).
- **Auditoría general del estado actual de la herramienta, 2026-07-31.**
  El consultor pidió una revisión seria y honesta de todo el proyecto
  ("ojo clínico, profesional y sincero"), considerando que ya maduró,
  para encontrar ajustes que no se hubieran detectado antes. Se auditó
  `domain`/`application`, toda la carpeta `ui/` (asistente y Modo
  Avanzado), la suite de tests y la documentación completa. Hallazgos
  reales corregidos en esta misma pasada:
  - `ui/panels/procesamiento_panel.py`: `_on_procesar_siguiente` y
    `_on_procesar_todos` eran los únicos dos manejadores de botón de
    toda la interfaz sin `try/except` -- un fallo de la capa de
    persistencia (no de la cola de trabajos en sí, que ya captura sus
    propios errores) podía subir sin capturar desde un slot de Qt.
    Corregido con el mismo patrón que el resto del panel.
  - `ui/panels/pruebas_panel.py`: el docstring y la
    `etiqueta_explicacion` todavía hablaban de "etapas anteriores" y de
    poder "pasar directo a Cerrar lote" -- texto que solo tenía sentido
    cuando esta pantalla era la Etapa 9 del asistente. Reescrito para
    explicar, sin ambigüedad, que es una herramienta de QA de Modo
    Avanzado independiente de cualquier proyecto en curso.
  - `ui/panels/markdown_panel.py`: `boton_manifiesto`/`barra_manifiesto`
    renombrados a `boton_preparar_entrega`/`barra_entrega`, acordes a lo
    que el botón hace hoy (nombre interno desalineado, sin impacto
    funcional).
  - `application/documents/commands/registrar_documento.py`: si el
    mismo contenido se registraba con un nombre de archivo distinto al
    ya inventariado, `copiar_original` completaba una copia física
    nueva en `01_originales/` antes de detectar el hash duplicado,
    dejando esa copia huérfana en disco para siempre. Corregido con una
    limpieza best-effort de esa copia (solo si es distinta de la ya
    registrada, nunca se toca el archivo legítimo). Prueba de humo
    ampliada (`test_registrar_documento_extremo_a_extremo.py`) para
    confirmar que `01_originales/` conserva solo la copia legítima tras
    el intento de duplicado.
  - Gap de cobertura real: el `QMessageBox` agregado a
    `EtapaCerrarLote` (entrada anterior de esta bitácora) no tenía
    ninguna prueba que distinguiera `.information` (entrega exitosa) de
    `.warning` (entrega fallida). Agregada la verificación en el
    recorrido completo existente más un test nuevo,
    `test_cierre_de_lote_avisa_con_advertencia_si_falla_la_entrega_a_rag_studio`,
    que fuerza el fallo de `preparar_entrega_rag_studio()` por
    monkeypatch para confirmar la rama de advertencia.
  - Documentación desactualizada: `Manual_de_Usuario_RAG_Content_Studio_Desktop.docx`
    todavía describía diez etapas y dedicaba la sección completa 5.3.9
    a "Ejecutar pruebas" (ya eliminada del asistente), además de
    describir el botón viejo "Generar manifiesto de entrega" en vez del
    actual "Preparar entrega para RAG Studio" -- corregido: nueve
    etapas, sección de cierre de lote renumerada a 5.3.9, y la
    descripción del botón actualizada. `MANUAL_OPERACION.md` contaba 13
    subcarpetas en vez de 14 (faltaba `14_entrega_rag_studio/`) y
    seguía diciendo que no existía pantalla GUI para respaldos, cuando
    `ConfiguracionPanel` ya la tiene desde la Fase 11 -- ambas
    corregidas. El campo "Estado" del propio Documento Maestro decía
    "construcción pendiente" pese a que su propia bitácora ya
    documentaba la interfaz completa -- actualizado para reflejar el
    estado real.
  - Sin hallazgos graves: la arquitectura hexagonal se mantiene sin
    violaciones (cero imports de PySide6/infraestructura en
    `domain`/`application`), sin código muerto relevante, y el resto
    del manejo de errores es consistente en todo el proyecto.
  - Ruff, Mypy (110 archivos entre `application/` y `ui/`) y Bandit
    limpios en todos los archivos tocados; 372 tests de
    `tests/unit/application/`, 164 de `tests/unit/domain/` +
    `test_registrar_documento_extremo_a_extremo.py` en verde.
- **Segunda auditoría general, con varias pasadas por área, 2026-07-31.**
  El consultor pidió repetir la auditoría anterior, considerando que la
  herramienta siguió madurando, "dando la cantidad de pasadas que
  [se] crea pertinente". Se profundizó en `domain`/`application`
  (invariantes de negocio en los puntos donde varios contextos se
  cruzan: cerrar lote, gobernanza, actas), en `ui/` (paneles que la
  primera ronda no había revisado a fondo: incidencias, normalización,
  reportes, configuración, proyectos, vigencias, inventario, auditoría,
  `dialogs.py` completo), en la cobertura de tests de módulos más
  antiguos (incidencias, validez/fuentes, gobernanza, colas de trabajo,
  transcripción, reportes) y en seguridad/rendimiento/recursos
  transversal. Hallazgos reales corregidos:
  - `application/reports/commands/generar_acta_cierre_lote.py`: el acta
    reportaba el mismo motivo ("revisar Fuente/Aprobación") para
    **cualquier** documento bloqueado al cerrar un lote, sin importar si
    de verdad llegó a VALIDADO y falló ahí, o si nunca pasó de una etapa
    anterior (extracción, revisión, normalización...) -- en ese segundo
    caso, Fuente/Aprobación no tiene nada que ver, y el acta (el
    documento que el operador lee para saber "por qué" se bloqueó cada
    uno) daba el motivo equivocado en casi todos los casos. Corregido
    distinguiendo ambos casos: `Documento.avanzar_a()` nunca limpia
    otros campos al cambiar de estado, así que `ruta_markdown` (fijado
    justo antes de VALIDADO) sigue presente en el documento ya
    BLOQUEADO si y solo si alcanzó a llegar hasta ahí -- señal
    suficiente para dar el motivo correcto sin necesitar un historial de
    estados aparte. Dos tests nuevos en
    `test_generar_acta_cierre_lote.py`.
  - `application/batches/commands/cerrar_lote.py`: solo dejaba un
    resumen agregado en la auditoría al final de `execute()` -- a
    diferencia de `RecuperarDocumentosInterrumpidos` (mismo patrón de
    "loop + guardar + auditar"), que sí audita cada elemento dentro del
    ciclo. Si `document_repository.save()` fallara a mitad del lote
    (disco lleno, lock de SQLite), los documentos ya resueltos en esa
    corrida quedaban sin ningún rastro individual en la auditoría.
    Corregido agregando un evento `cerrar_lote_documento` por cada
    documento que sí cambia de estado (con su transición real,
    `valor_anterior`/`valor_nuevo`), sin quitar el resumen agregado
    final. Test nuevo en `test_cerrar_lote.py`.
  - `ui/panels/incidencias_panel.py`: era el único panel de toda la
    interfaz donde, si el operador confirmaba el diálogo (Asignar/
    Responder/Decidir/Cerrar) con el campo obligatorio vacío, no pasaba
    nada -- sin ningún aviso de por qué. Corregido con
    `QMessageBox.warning("Campo requerido", ...)` en los cuatro botones,
    igual que el resto de la interfaz; se distingue de cancelar el
    diálogo (eso sigue sin avisar nada, es una elección válida del
    operador). Test nuevo en `test_gui_menu_completo_extremo_a_extremo.py`.
  - `ui/main_window.py`: ni `_on_abrir_proyecto()` cerraba la `Session`
    de SQLAlchemy del proyecto anterior al abrir uno nuevo, ni existía
    ningún `closeEvent` que cerrara las sesiones al salir de la
    aplicación -- ambas fugas dejaban conexiones SQLite abiertas hasta
    que terminara el proceso. Corregido cerrando la sesión anterior
    antes de reemplazar `self.pctx`, y agregando
    `MainWindow.closeEvent()` que cierra tanto la sesión del proyecto
    abierto (si hay uno) como la sesión global de `AppContext`. Dos
    tests nuevos en `test_pantalla_principal_extremo_a_extremo.py`.
  - `infrastructure/extraction/txt_markdown_extractor.py`: leía el
    archivo completo con `Path.read_text()` en vez de por bloques como
    `_hash_sha256_de()` -- una inconsistencia de criterio real, aunque
    no explotable (el contrato del Módulo 12 exige el contenido
    literal completo como un solo string; leer por bloques no ahorraría
    memoria, terminaría igual con el archivo entero materializado antes
    de poder devolverlo). Se documentó la diferencia como una decisión
    deliberada en vez de dejarla como un silencio sin explicar,
    consistente con el criterio de este proyecto de nunca dejar una
    desviación sin justificar.
  - Sin hallazgos graves adicionales: seguridad (rutas, cifrado,
    limpieza de temporales, protección zip-slip ya implementada),
    rendimiento (listas sin paginación, aceptable para el alcance) y la
    cobertura de tests de los módulos más antiguos quedaron en buen
    estado tras revisar a fondo -- no se fuerzan hallazgos donde
    genuinamente no los hay.
  - Ruff, Mypy y Bandit limpios en todos los archivos tocados; 374
    tests de `tests/unit/application/` en verde (2 más que la ronda
    anterior, por los tests nuevos de acta de cierre y auditoría de
    lote).
- **Tercera auditoría, con autocorrección real sobre el propio trabajo
  del día, 2026-07-31.** El consultor pidió repetir la auditoría una
  vez más tras aplicar las 5 correcciones anteriores. El hallazgo más
  importante de esta ronda fue sobre el propio arreglo recién hecho:
  - `application/reports/commands/generar_acta_cierre_lote.py`: el
    `_motivo_riesgo()` agregado en la ronda anterior usaba
    `documento.ruta_markdown is not None` como señal de que un
    documento bloqueado había llegado a VALIDADO -- pero esa señal
    tiene un falso positivo real: un documento puede llegar a
    MARKDOWN_GENERADO (que ya fija `ruta_markdown`, vía
    `generar_markdown()`) sin haber pasado todavía por
    `validar_markdown()` -- son dos comandos separados, invocados por
    botones distintos en `markdown_panel.py`. Ese documento nunca pasa
    por el chequeo de gobernanza (`CerrarLote` solo lo hace si
    `estado == VALIDADO`), así que "`ruta_markdown` no nulo" NO
    implica "gobernanza falló". Corregido de raíz: en vez de inferir el
    pasado desde un campo que no fue diseñado para eso, ahora se
    pregunta por el **presente** -- se re-ejecuta la misma verificación
    de gobernanza que `CerrarLote` ya usó
    (`GovernanceService.verificar_documento_liberable()`, que no
    depende del estado del documento, solo mira si hay Fuente y
    Aprobación registradas), distinguiendo tres motivos reales: falta
    Fuente, falta Aprobación, o ya tiene ambas pero no completó la
    validación del Markdown. `GenerarActaCierreLote` ahora depende
    también de `GovernanceService` (wiring actualizado en
    `application/reports/service.py`, ya recibía esa dependencia para
    `GenerarInformeCalidad`). Tests reescritos en
    `test_generar_acta_cierre_lote.py`, cubriendo los tres casos reales
    por separado.
  - Documento Maestro, sección 4.11: seguía listando el flujo viejo del
    asistente con diez pasos, incluyendo "ejecutar pruebas" -- quedó
    inconsistente consigo mismo (la portada, corregida en la entrada
    anterior, ya decía "asistente de nueve etapas"). Corregido.
  - Otros hallazgos de esta ronda, presentados al consultor para
    decidir si se aplican (ver conversación): `EtapaAprobar` del
    asistente descarta el comentario de aprobación (pasa cadena vacía
    fija, a diferencia de Modo Avanzado); el modo en segundo plano de
    `ColaDeTrabajos` (`ThreadPoolExecutor`) no sería seguro contra
    SQLite si algún día se activa con más de un hilo (hoy nunca se
    invoca en producción, solo está probado contra un fake en memoria);
    tres puntos de la UI cargan perfiles YAML sin capturar errores de
    validación (traceback crudo en vez de mensaje amigable); falta un
    índice en `eventos_auditoria.proyecto_id` (más relevante ahora que
    `CerrarLote` audita por documento); los scripts de mantenimiento no
    envuelven errores específicos del dominio.
  - Ruff, Mypy y Bandit limpios en los archivos tocados; tests de
    `generar_acta_cierre_lote`, `reports_service` y
    `ejecutar_pruebas_aceptacion` en verde.
- **Aplicación de las 5 correcciones pendientes de la tercera auditoría,
  2026-08-01.** El consultor pidió aplicar los 5 hallazgos que la ronda
  anterior había dejado solo presentados, sin tocar código:
  - `ui/wizard/etapas.py` (`EtapaAprobar`): el asistente descartaba el
    comentario de aprobación, pasando siempre `""` a
    `aprobar_para_markdown()` -- a diferencia de Modo Avanzado, que sí
    lo captura. Corregido agregando el campo "Comentario (opcional)" al
    formulario y pasando su valor real. Test actualizado en
    `test_asistente_por_etapas_extremo_a_extremo.py`, verificando el
    comentario guardado en la `Aprobacion` resultante.
  - `workers/cola_de_trabajos.py`: el modo en segundo plano
    (`ThreadPoolExecutor`) no tiene ninguna garantía de ser seguro
    contra la `Session` de SQLAlchemy real (creada en un solo hilo, sin
    `check_same_thread=False` ni sesión por hilo) -- hoy nunca se activa
    en producción, solo está probado contra fakes en memoria, pero
    activarlo alguna vez contra `app.bootstrap.bootstrap()` real
    arriesgaría corrupción silenciosa de datos. Corregido exigiendo
    `permitir_segundo_plano=True` explícito en el constructor para que
    `iniciar()` funcione; el wiring real de producción
    (`app/bootstrap.py`) sigue en su valor por defecto seguro (`False`).
    Test nuevo en `test_cola_de_trabajos.py` confirmando el
    `RuntimeError` claro cuando no se pasa ese flag.
  - Tres puntos de la UI cargaban perfiles YAML sin capturar errores de
    validación, dejando pasar un traceback crudo en vez de un aviso
    amigable ante un YAML corrupto (campo obligatorio faltante, archivo
    vacío, versión mal nombrada): `ui/wizard/etapas.py`
    (`EtapaProyectoPerfil._on_crear_proyecto()`),
    `ui/panels/proyectos_panel.py` (`_on_crear_proyecto()`) y
    `ui/panels/configuracion_panel.py` (`_cargar_perfiles()`). Los tres
    corregidos con el mismo patrón ya usado en el resto de la interfaz:
    `try/except Exception` + `QMessageBox.critical(...,
    mensaje_amigable(exc))`.
  - `infrastructure/database/models.py`
    (`EventoAuditoriaModel.proyecto_id`): sin índice, a pesar de que
    desde la corrección anterior `CerrarLote` audita cada documento por
    separado además del evento agregado -- el volumen de
    `eventos_auditoria` ahora crece con la cantidad de documentos por
    lote, no solo con la cantidad de lotes, y cualquier consulta futura
    que filtre por proyecto haría un table scan completo de la tabla
    global. Corregido agregando `index=True` a la columna y una
    migración nueva en la línea global
    (`migrations/global/versions/3ab8296484bc_...py`), verificada con
    `alembic upgrade`/`downgrade` reales contra una base SQLite temporal
    y con `alembic revision --autogenerate` confirmando diff vacío
    (modelo y migración ya coinciden). Test nuevo en
    `test_migrations.py`.
  - `scripts/gestionar_respaldos.py` y
    `scripts/ejecutar_pruebas_aceptacion.py`: ninguno de los dos
    capturaba errores específicos del dominio (por ejemplo,
    `ClaveDeRespaldoNoEncontradaError` al restaurar sin clave guardada),
    dejando pasar un traceback completo de Python en la terminal.
    Corregido envolviendo el cuerpo de `main()` en `try/except Exception`
    e imprimiendo `str(exc)` (los mensajes de las excepciones de dominio
    de este contexto ya están redactados en español y son accionables
    por sí mismos) con código de salida 1 -- sin acoplar estos scripts a
    `ui.errores.mensaje_amigable`, ya que `scripts/` no es una capa de
    ADR-001 y no debe depender del paquete de la interfaz gráfica. Tests
    nuevos en `tests/unit/scripts/` (carpeta nueva), monkeypencheando el
    punto de entrada a `app.bootstrap` para forzar cada tipo de fallo
    sin necesitar una base de datos real.
  - Ruff, Mypy (209 archivos de `domain`, `application`, `infrastructure`,
    `ui`, `workers` y `scripts`) y Bandit limpios -- los 2 hallazgos de
    Bandit siguen siendo los mismos `B110` ya justificados de siempre,
    nunca una regresión. 564 pruebas en verde (375 en
    `tests/unit/application/`, 189 en `tests/unit/domain`,
    `tests/unit/app`, `tests/unit/ui`, `tests/unit/workers/` y el nuevo
    `tests/unit/scripts/`); los archivos de humo tocados
    (`test_asistente_por_etapas_extremo_a_extremo.py`) verificados por
    `py_compile` (entorno sin bibliotecas gráficas, limitación conocida
    y aceptada desde el primer prototipo).
- **Cuarta auditoría general, con múltiples pasadas por área, 2026-08-01.**
  El consultor pidió repetir la auditoría una vez más. Se usaron cinco
  subagentes en paralelo, cada uno con varias pasadas internas y con
  instrucciones explícitas de no forzar hallazgos donde no los hay:
  `domain`/`application`, `ui`, tests, documentación y
  seguridad/rendimiento/consistencia transversal. A diferencia de rondas
  anteriores, esta vez ningún hallazgo se corrigió de inmediato -- los
  doce hallazgos reales se presentaron completos al consultor para
  decidir en bloque (ver la entrada siguiente para la aplicación real):
  - `domain`/`application` (4 hallazgos): `CorregirExtraccion` escribía
    en disco antes de validar el estado del documento; `AgregarDocumentoALote`
    no comprobaba si el lote de ORIGEN del documento ya estaba cerrado
    (asimetría real frente a `QuitarDocumentoDeLote`, que sí lo hace);
    `generar_manifiesto`/`preparar_entrega_rag_studio` producían en
    silencio un resultado vacío ante un `lote_id` inexistente; lógica de
    parseo de versión de perfil duplicada en dos módulos, lanzando
    `ValueError` crudo en vez de una excepción de dominio.
  - `ui` (2 hallazgos): Modo Avanzado no tenía ningún panel para
    crear/cerrar lotes (solo el asistente, y solo al final del flujo);
    `ui/panels/pruebas_panel.py` escribía el informe de aceptación sin
    ningún `try/except`.
  - tests (3 hallazgos): `CrearProyecto` no tenía ninguna prueba
    unitaria propia, solo cobertura indirecta vía prueba de humo;
    `tests/smoke/` mezclaba pruebas de integración reales sin GUI con
    pruebas de GUI real, arriesgando que se saltaran en el ciclo rápido
    de desarrollo bajo el supuesto equivocado de que "smoke = necesita
    GUI"; los fakes `_FakeAuditLogger`/`_FakeDocumentRepository` estaban
    duplicados, prácticamente palabra por palabra, en unos 24 archivos
    de prueba.
  - documentación (1 hallazgo): la sección 5.3.7 del Manual de Usuario
    no mencionaba el campo opcional "Comentario" agregado a la etapa de
    aprobación del asistente en la ronda anterior.
  - seguridad/rendimiento (2 hallazgos): tanto el panel de auditoría
    como el dashboard cargaban el historial completo de auditoría sin
    ningún `LIMIT`; `ui/panels/pruebas_panel.py` instanciaba un
    adaptador de `infrastructure` directamente en vez de recibirlo desde
    `app/bootstrap.py` -- la única inconsistencia arquitectónica real
    que quedaba en toda la capa `ui/`.
  - Sin hallazgos graves adicionales tras las cinco pasadas.
- **Aplicación de los 12 hallazgos de la cuarta auditoría, 2026-08-01.**
  El consultor aprobó aplicar los doce de una vez ("sí, adelante").
  Corregidos:
  - `application/documents/commands/corregir_extraccion.py`: ahora
    valida `documento.estado == EstadoDocumento.EXTRAIDO` (lanzando
    `CorreccionRequiereEstadoExtraidoError`) ANTES de escribir el
    markdown corregido en disco -- mismo orden ya corregido antes en
    `registrar_documento.py`. Test nuevo confirmando que, ante estado
    inválido, no se escribe nada.
  - `application/batches/commands/agregar_documento_a_lote.py`: agrega
    la misma comprobación de lote de origen cerrado que ya tenía
    `QuitarDocumentoDeLote` -- antes, un documento se podía sacar en
    silencio de un lote CERRADO con solo agregarlo a otro lote ABIERTO.
    Dos tests nuevos (lote de origen cerrado falla; lote de origen
    huérfano no bloquea, mismo criterio que el caso ya cubierto de
    `QuitarDocumentoDeLote`).
  - `application/documents/commands/generar_manifiesto.py`: ahora
    depende de `LoteRepository` y valida que el `lote_id` exista antes
    de filtrar (lanza `BatchNotFoundError`) -- antes, un id con error de
    tipeo o de un lote ya borrado generaba en silencio un
    manifiesto/carpeta de entrega vacíos. Cambio más invasivo de esta
    ronda: requirió reordenar la construcción en `app/bootstrap.py` (el
    `LoteRepository` ya existía, solo se adelantó su creación) y
    actualizar unos nueve puntos de construcción en pruebas.
    `PrepararEntregaRagStudio` hereda la protección gratis, al reusar el
    mismo caso de uso. Tests nuevos en ambos archivos.
  - `domain/profiles/entities.py`: nueva función `clave_version()` con
    la excepción de dominio `VersionDePerfilInvalidaError`, sustituyendo
    el `_clave_version()` duplicado (con `ValueError` crudo) que vivía
    por separado en `application/profiles/commands/publicar_nueva_version.py`
    e `infrastructure/filesystem/profile_loader.py` -- ambos ahora
    importan la versión única. Tests nuevos verificando el orden
    semántico y la excepción de dominio.
  - `ui/panels/pruebas_panel.py`: ya no instancia
    `MarkdownInformeAceptacionWriter` directamente -- ahora lo recibe
    desde `ProjectContext.informe_aceptacion_writer` (construido en
    `app/bootstrap.py`), y la escritura del informe queda protegida con
    `try/except` + `QMessageBox.critical(..., mensaje_amigable(exc))`,
    mismo patrón que el resto de la interfaz.
  - `domain/projects/ports.py` / `infrastructure/database/audit_logger.py`:
    `AuditLogger.list_by_project()` gana un parámetro
    `limite: Optional[int] = None` que aplica un `LIMIT` real en SQL (no
    un post-filtrado en Python). `ui/dashboard/pantalla_principal_widget.py`
    y `ui/panels/auditoria_panel.py` (nuevo límite de 500, con aviso
    visible si se alcanza) ahora lo usan.
  - `tests/unit/application/test_create_project.py` (archivo nuevo): 5
    pruebas unitarias para `CrearProyecto`, que antes solo tenía
    cobertura indirecta vía prueba de humo.
  - `tests/smoke/` reorganizado: 12 archivos que en realidad no dependen
    de PySide6/qtbot (`bootstrap()`/`abrir_proyecto()` reales, sin GUI)
    se movieron a `tests/integration/` (carpeta nueva); solo quedan en
    `tests/smoke/` los 6 archivos que sí requieren Qt/EGL real.
  - `tests/unit/application/_fakes.py` (archivo nuevo): `_FakeAuditLogger`/
    `_FakeDocumentRepository` consolidados ahí, verificados como
    duplicados byte a byte (o compatibles) antes de mover nada; 25
    archivos de prueba actualizados para importarlos en vez de
    redefinirlos. `_FakeVigenciaRepository`/`_FakeIncidentRepository`,
    también señalados por la auditoría, resultaron tener más variación
    real entre archivos de lo que la auditoría estimó -- se documentan
    como trabajo futuro en vez de forzar una consolidación insegura.
  - `Manual_de_Usuario_RAG_Content_Studio_Desktop.docx`, sección 5.3.7:
    agregado el bullet del campo opcional "Comentario" de la etapa de
    aprobación del asistente, con referencia cruzada a donde ya se
    documentaba en Modo Avanzado (sección 6.8).
  - `ui/panels/lotes_panel.py` (archivo nuevo): Modo Avanzado ahora
    tiene una pantalla "Lotes" (entre "Reportes" y "Auditoría" en el
    menú) para crear y cerrar lotes sin pasar por el asistente completo
    -- expone únicamente `BatchesService.crear_lote()`/`cerrar_lote()`
    (más listar, para ver el estado y la cantidad de documentos de cada
    uno), mismo patrón que el resto de `ui/panels/*` (tabla + botones +
    `establecer_proyecto()`). `tests/smoke/test_gui_menu_completo_extremo_a_extremo.py`
    ampliado para crear y cerrar un lote real a través del panel nuevo
    (antes lo hacía directo contra la fachada, sin pasar por ninguna
    UI).
  - Ruff, Mypy (213 archivos de `domain`, `application`, `infrastructure`,
    `ui`, `workers`, `scripts` y `app`) y Bandit limpios en todo el
    proyecto -- los 2 hallazgos de Bandit siguen siendo los mismos
    `B110` ya justificados desde siempre. 609 pruebas no-GUI en verde
    (388 en `tests/unit/application/`, 221 entre `tests/unit/domain`,
    `tests/unit/app`, `tests/unit/ui`, `tests/unit/workers`,
    `tests/unit/scripts` y el nuevo `tests/integration/`). Además, esta
    vez sí se pudo ejecutar la suite completa de `tests/smoke/` (30
    pruebas de GUI real) en este mismo entorno de trabajo -- a
    diferencia de rondas anteriores, que solo podían verificarse por
    `py_compile` (bibliotecas gráficas ausentes, o eso se creía: existen
    en `~/localqtlibs`, solo hacía falta `LD_LIBRARY_PATH` apuntando
    ahí): 29 en verde, 1 falla preexistente y ajena a esta ronda
    (`test_paneles_de_documentos_y_estado_se_pueden_ocultar_y_mostrar`,
    en un archivo que esta ronda no tocó -- falla igual en aislamiento,
    sin ningún cambio de esta ronda) -- se deja fuera de esta ronda, sin
    aprobación del consultor todavía para investigarla y corregirla.
- **Investigación y corrección de la falla preexistente de
  `test_paneles_de_documentos_y_estado_se_pueden_ocultar_y_mostrar`,
  2026-08-01.** El consultor pidió investigar la falla dejada pendiente
  en la entrada anterior. No era un bug de la aplicación: eran dos bugs
  del propio test, invisibles hasta ahora porque nunca se había podido
  ejecutar `tests/smoke/` de verdad en este entorno. Primero, el test
  nunca llamaba `ventana.show()` -- sin exponer la ventana de verdad,
  `isVisible()` de cualquier widget hijo es `False` por semántica normal
  de Qt, sin relación con el bug que se quería probar. Segundo, el test
  nunca entraba de verdad a "Modo avanzado": `_ir_a_revision()` solo
  cambia `lista_navegacion`, que vive DENTRO de la página "Modo
  avanzado" de `modo_stack` (índice 2) -- pero `_on_abrir_proyecto()`
  (Fase 11.3) navega automáticamente a "Asistente" (índice 1) al abrir
  un proyecto desde "Inicio", así que sin cambiar de modo explícitamente
  la página "Revisión" quedaba seleccionada dentro de un stack que nunca
  era el visible; y `radio_modo_avanzado.setChecked(True)` tampoco
  alcanza para eso, porque `MainWindow._on_cambiar_modo` está conectado
  a `grupo_modos.idClicked`, una señal que solo se dispara con un clic
  real, no al fijar el estado del botón a mano. Confirmado con un script
  de reproducción manual (`ventana.show()` + `radio_modo_avanzado.click()`
  + `processEvents()`) que el feature en sí -- ocultar/mostrar los
  paneles de "Revisión" -- nunca estuvo roto: ambos paneles se ocultan y
  muestran correctamente. Corregido el test agregando
  `qtbot.waitExposed(ventana)` alrededor de `ventana.show()` y
  reemplazando la navegación implícita por `ventana.radio_modo_avanzado.click()`
  antes de `_ir_a_revision()`. Las 7 pruebas de
  `test_gui_revision_incidencias_extremo_a_extremo.py` y las 30 de toda
  `tests/smoke/` en verde. Ruff y Mypy limpios (sin cambios de alcance
  en `domain`/`application`/`infrastructure`/`ui`/`workers`/`scripts`/`app`).
- **Nivel 1 (confianza de OCR) y Nivel 2 (validaciones numéricas) de
  asistencia a la revisión contra el original, 2026-08-01.** El
  consultor preguntó qué tanto aportaría usar algo como OpenCV (o
  similar) para que la herramienta "lea" el documento original y coteje
  automáticamente contra lo extraído, dado que el revisor procesa
  volúmenes altos de documentos en "Revisión" y esa tarea depende de su
  agudeza visual. El análisis presentado distinguió tres niveles: (1)
  superficie de la confianza por palabra que Tesseract ya calcula pero
  antes se descartaba; (2) validaciones numéricas/estructurales
  objetivas (totales de tabla, fechas imposibles); (3) un LLM de visión
  como segundo lector independiente -- este último requeriría un motor
  externo nuevo y juicio semántico que OpenCV por sí solo no da. El
  consultor aprobó implementar los Niveles 1 y 2 ("ya casi está pagado,
  el dato existe"), dejando el Nivel 3 fuera de esta ronda. En ambos
  niveles se preserva el criterio de Módulo 13 (control humano): nada se
  corrige solo, todo se resalta para que el revisor decida.
  - **Nivel 1 (confianza de OCR):** `domain.documents.
    ocr_table_reconstruction.PalabraOcr` gana el campo `confianza`
    (0-100, el valor `conf` que `pytesseract.image_to_data()` ya
    calculaba y que `TesseractOcrEngine` solo usaba como filtro binario
    `> -1` y luego tiraba). `reconstruir_texto_ocr()` ahora devuelve un
    tercer valor, `rangos_baja_confianza: list[RangoBajaConfianza]`
    (`UMBRAL_CONFIANZA_BAJA = 60.0`, constante de módulo ajustable),
    ubicando en el texto reconstruido los tramos que corresponden a
    palabras por debajo del umbral -- localización por búsqueda
    secuencial hacia adelante, deliberadamente simple: en el peor caso
    resalta una aparición vecina de la misma palabra, nunca una palabra
    distinta ni lanza una excepción. El campo se hizo llegar por las
    cuatro capas: `TesseractOcrEngine`/`PdfOcrExtractor`/
    `ImageOcrExtractor` (ajustando el recorte por `.strip()` para no
    invalidar los rangos), `ResultadoExtraccion`/`Documento`/
    `completar_extraccion()` (mismo criterio de "aproximación aceptada"
    que ya documentaba `mapa_paginas`: `Documento.corregir()` no
    recalcula los rangos), y la persistencia SQLAlchemy
    (`DocumentoModel.rangos_baja_confianza_json`, migración
    `a1de6fc9583f`, mismo patrón `server_default='[]'` que
    `mapa_paginas_json`, verificada con upgrade/downgrade/re-upgrade y
    diff vacío de autogenerate). En la UI, `MainWindow.
    _resaltar_baja_confianza()` resalta esos tramos en el panel
    "Extraído / revisado" con `QTextEdit.ExtraSelection` (fondo ámbar,
    primer uso de ese mecanismo de Qt en todo `ui/`), con una etiqueta
    resumen ("N palabra(s) resaltada(s)...") y descartando en silencio
    cualquier rango que ya no encaje en el texto vigente.
  - **Nivel 2 (validaciones numéricas):** `HallazgoVerificacion` (ya
    existente, deteccion de fechas/cifras) gana el campo opcional
    `advertencia`. Para fechas, `detectar_fechas_y_cifras()` ahora
    también valida el calendario -- por ejemplo "31/04/2026" (abril
    solo tiene 30 días) o "29/02/2026" (2026 no es bisiesto) -- sobre
    los tres formatos que ya detectaba (numérico DD/MM/AAAA -- la
    convención de este proyecto y sus documentos --, ISO, y en español
    con el mes escrito), expandiendo años de 2 dígitos como 20XX. Esto
    SÍ es una validación real (un hecho objetivo de calendario, no una
    opinión), a diferencia de la detección de fechas/cifras en sí, que
    sigue sin juzgar si la fecha es la correcta para el contrato. Nuevo
    módulo `domain/documents/verificacion_totales_tabla.py`: parsea
    tablas Markdown (encabezado + fila separadora + filas de datos,
    mismo formato que ya emite `ocr_table_reconstruction`), identifica
    la fila de "Total"/"Totales"/"Suma"/"Gran total" por el nombre de su
    primera celda no vacía, y valida columna por columna (de forma
    independiente entre sí) que la suma de las demás filas coincida con
    esa fila -- con un parser de números ambiguos
    (`_parsear_numero_ambiguo()`) que resuelve cuál de `,`/`.` es el
    separador decimal según cuál aparece más a la derecha (si aparecen
    ambos) o según la cantidad de dígitos que le siguen (si aparece solo
    uno). En la UI, `MainWindow._mostrar_verificaciones()` combina los
    hallazgos de ambas fuentes en una sola lista ordenada por posición;
    los que traen `advertencia` se resaltan en el mismo ámbar que Nivel
    1 (mismo lenguaje visual de "revisar con más cuidado" en toda la
    pantalla), con el motivo como tooltip.
  - Pruebas nuevas: 6 en `test_ocr_table_reconstruction.py`, 2 en
    `test_entities_documento.py` y 1 en
    `test_sqlalchemy_document_repository.py` (round-trip real de
    `rangos_baja_confianza`, mismo patrón que ya cubría `mapa_paginas`
    -- brecha detectada y cerrada en esta misma ronda), 11 en
    `test_verificacion_fechas_cifras.py` (19 en total), 15 en el nuevo
    `test_verificacion_totales_tabla.py`, más 2 pruebas de humo nuevas
    (resaltado de baja confianza y verificaciones de Nivel 2 en
    `test_gui_revision_incidencias_extremo_a_extremo.py`) -- todas
    verdes. Ruff y Mypy limpios en los 209 archivos fuente de
    `domain`/`application`/`infrastructure`/`ui`/`app`; Bandit sin
    hallazgos nuevos (los 2 `B110` preexistentes, ajenos a esta ronda,
    siguen igual de justificados). Suite completa verde: 198 pruebas en
    `tests/unit/domain`, 26 en `tests/unit/app`+`scripts`+`workers`+`ui`,
    388 en `tests/unit/application` (1 prueba deliberadamente fuera,
    `test_faster_whisper_engine.py::...real...`: requiere red a
    Hugging Face, bloqueada por el proxy de este entorno -- limitación
    preexistente y documentada, ajena a esta ronda), 30 en
    `tests/integration`, y las 32 de `tests/smoke` (incluidas las 2
    nuevas de esta ronda).
- **Preprocesamiento de OCR (RAG STUDIO) + deskew propio en
  `TesseractOcrEngine`, 2026-08-24.** El consultor compartió cuatro
  artículos sobre herramientas RAG (Meilisearch, LIDR, Firecrawl,
  Progress) preguntando si RAG Content Studio ya cubre lo que describen
  y si hay algo de valor implementable sin complicar la operación del
  usuario; el análisis concluyó que la única brecha real y aprovechable
  (un `document_type_code` por documento en el manifiesto de entrega,
  que RAG STUDIO podría usar para elegir su estrategia de fragmentación
  automáticamente) queda fuera de alcance por ahora -- RAG STUDIO ya
  fragmenta de forma consciente de encabezados/tablas directamente sobre
  el Markdown, sin necesitar un archivo lateral. A continuación el
  consultor compartió un tutorial de OpenCV+Pytesseract y pidió analizar
  si incorporar OpenCV, lo ya implementado en RAG STUDIO (el proyecto
  hermano, que ya tiene su propio motor Tesseract con preprocesamiento
  en PIL puro, sin OpenCV/numpy), o una combinación de ambos mejora la
  capacidad de OCR de RAG Content Studio. El análisis concluyó que
  OpenCV no aporta valor proporcional a su peso como dependencia nueva
  para lo que se necesita aquí, y que el preprocesamiento de RAG STUDIO
  (escala de grises, filtro de medianas, binarización con umbral de
  Otsu, y recuperación de bandas de encabezado con fondo de color vía
  análisis HSV) sí es una mejora de valor, portable sin depender de
  OpenCV/numpy. El consultor aprobó portarlo e incluir además una
  corrección de inclinación (deskew), que no existe en ninguno de los
  dos proyectos, "integrados de la mejor manera posible" con el Nivel 1
  ya existente.
  - `TesseractOcrEngine` (`infrastructure/extraction/
    tesseract_ocr_engine.py`) gana preprocesamiento opcional (activado
    por defecto, parámetro `preprocess`, retrocompatible con la
    construcción sin argumentos que ya usaba `app/bootstrap.py`)
    adaptado de RAG STUDIO: `_preprocesar_para_ocr()` aplica escala de
    grises, reducción de ruido (`ImageFilter.MedianFilter`) y
    binarización con un umbral de Otsu calculado en Python puro
    (`_umbral_otsu()`) antes de pasar la imagen a Tesseract;
    `_detectar_bandas_de_color()`/`_recuperar_texto_de_bandas_de_color()`
    detectan y reconocen por separado los encabezados con fondo de
    color saturado que Tesseract normalmente omite por completo (vía
    HSV; el recorte de la banda deliberadamente NO se preprocesa, porque
    el filtro de medianas destruye trazos finos en recortes pequeños),
    agregando ese texto al final del resultado con una advertencia
    explícita.
  - Deskew, aporte propio de esta ronda (RAG STUDIO no lo tiene):
    `_detectar_angulo_inclinacion()` busca, sobre una miniatura de hasta
    700px de ancho (mismo resultado que sobre la imagen original, costo
    acotado), el ángulo entre -5° y 5° (en pasos de 0.5°) que maximiza
    la nitidez del perfil de proyección horizontal
    (`_perfil_de_proyeccion()`: contraste fila a fila de brillo
    promedio, calculado con `Image.resize` a una sola columna en vez de
    iterar píxel por píxel en Python); si ningún candidato mejora al
    menos un 5% sobre no rotar nada, no se rota nada (evita introducir
    rotación espuria en imágenes ya derechas, confirmado con una prueba
    dedicada).
  - Integración con el Nivel 1 (confianza de OCR) ya existente: todo el
    texto recuperado de bandas de color se marca con confianza `0.0`
    (`RangoBajaConfianza`), siempre por debajo del umbral de `60.0`, así
    que se resalta en ámbar en la UI de "Revisión" sin necesitar ningún
    código nuevo de interfaz -- reutiliza el mecanismo que ya existía
    para la confianza por palabra de Tesseract.
  - Sin nuevas dependencias: todo implementado en PIL puro, sin OpenCV
    ni numpy, mismo criterio que ya documenta RAG STUDIO para su propio
    motor.
  - Pruebas nuevas: 7 en `test_tesseract_ocr_engine.py` (14 en total en
    ese archivo), cubriendo recuperación de texto en imágenes ruidosas,
    corrección de inclinación de extremo a extremo, detección del
    ángulo correctivo con tolerancia, no rotación de imágenes ya
    derechas, recuperación de bandas de color marcada como baja
    confianza, no degradación de imágenes ya nítidas, y no mutación de
    la imagen original -- todas calibradas empíricamente contra
    ejecuciones reales de Tesseract, no asumidas. Ruff y Mypy limpios en
    `tesseract_ocr_engine.py`; Bandit sin hallazgos nuevos (1 hallazgo
    Low preexistente en el patrón de recuperación por banda -- un
    `except Exception: continue` por diseño, para que el error de una
    sola banda no descarte las demás ni el resultado principal --
    suprimido con `# nosec B112` y justificación, mismo criterio que los
    demás `# nosec` ya documentados del proyecto). Suite completa verde
    en este entorno de desarrollo: 198 en `tests/unit/domain`, 26 en
    `tests/unit/app`+`scripts`+`workers`+`ui`, 396 en
    `tests/unit/application`, y 30 en `tests/integration` (incluida la
    cobertura real de extracción por OCR de extremo a extremo, que
    ejercita el nuevo preprocesamiento/deskew sin ningún cambio de
    comportamiento observable en los resultados ya esperados); las 32 de
    `tests/smoke` no se pudieron ejecutar en este entorno de desarrollo
    puntual por falta de la librería de sistema `libEGL.so.1` (sin
    acceso a `sudo` para instalarla) -- misma categoría de limitación de
    entorno ya documentada más abajo para el paquete de idioma `spa` de
    Tesseract, ajena a esta ronda y sin cambios de alcance en `ui/`.

- **Auditoría integral (bugs reales) y actualización completa del
  Manual de Usuario, 2026-08-24.** El consultor pidió una auditoría
  profunda para validar la posibilidad de errores en la herramienta y
  corregirlos hasta quedar resueltos, y al finalizar validar que el
  Manual de Usuario quedara completamente actualizado sin omitir ningún
  detalle. Se lanzaron cuatro subagentes de auditoría independientes
  (dominio/aplicación, infraestructura, UI, tests) y los hallazgos de
  mayor severidad se verificaron personalmente contra el código fuente
  real antes de aplicar ninguna corrección -- misma disciplina de
  "confirmar empíricamente, nunca asumir" de las rondas anteriores.
  - Seis correcciones aplicadas: (1) `_fila_es_total` (verificación de
    totales de tabla) usaba `palabra in texto`, así que una fila
    "Subtotal" activaba por subcadena la palabra clave "total" y podía
    tomarse por error como la fila de total real -- ahora usa patrones
    de palabra completa (`\bpalabra\b`); (2) un documento en estado
    OBSERVADO o BLOQUEADO no podía transicionar a BLOQUEADO, así que
    `CerrarLote` fallaba al intentar bloquear (en vez de liberar) un
    documento ya OBSERVADO -- se agregó BLOQUEADO a las transiciones
    permitidas desde ambos orígenes; (3) `TesseractOcrEngine` reventaba
    con una excepción cruda ante una imagen truncada/corrupta (ahora
    levanta `OcrEngineUnavailableError` con mensaje claro), dejaba
    espacio en blanco inicial sin recortar cuando el texto recuperado de
    una banda de color no tenía cuerpo reconocido, tragaba en silencio
    cualquier fallo al detectar bandas de color (ahora se reporta como
    advertencia), y no descartaba una página con un número implausible
    de "bandas de color" detectadas (falsos positivos en cascada); (4)
    cambiar de "Asistente" a "Modo avanzado" y volver no refrescaba la
    pantalla de destino con el proyecto actual; (5) el botón "Abrir
    carpeta de proyectos" de Configuración no capturaba `OSError` al
    crear la carpeta si no existía, y reventaba en vez de avisar; (6)
    `leer_etapa` (autoguardado del Asistente) prometía en su docstring
    "nunca lanza", pero un archivo con JSON válido y no-objeto (una
    lista, un número, `null`) hacía fallar `datos.get(...)` con
    `AttributeError`, fuera de la tupla de excepciones capturada.
  - Pruebas nuevas: 2 en `test_verificacion_totales_tabla.py`, 1 en
    `test_entities_documento.py`, 1 en `test_cerrar_lote.py`, 4 en
    `test_tesseract_ocr_engine.py`, 1 archivo nuevo
    `tests/unit/ui/test_estado_asistente.py` con 5 pruebas, y 2 en
    `tests/smoke/test_gui_menu_completo_extremo_a_extremo.py` (estas
    últimas solo verificadas por compilación y Ruff, no ejecutadas, por
    la misma limitación de entorno de `libEGL.so.1` ya documentada).
    Suite completa verde en este entorno: 201 en `tests/unit/domain`, 31
    en `tests/unit/app`+`scripts`+`workers`+`ui`, 401 en
    `tests/unit/application`, y 30 en `tests/integration` (663 en
    total, cero regresiones); las 34 de `tests/smoke` no se pudieron
    ejecutar aquí por la misma limitación preexistente. Ruff, Mypy y
    Bandit limpios en todos los archivos tocados.
  - Manual de Usuario: se corrigió el conteo de pantallas (12 -> 13) en
    dos lugares, se agregó la pantalla "Lotes" a la enumeración de la
    sección 6, y se agregó una sección nueva completa "6.11 Lotes" (con
    "6.11.1 Crear un lote" y "6.11.2 Cerrar un lote", incluyendo los
    mensajes de error propios de esa pantalla y la aclaración de que,
    a diferencia de la etapa 9 del Asistente, cerrar un lote desde ahí
    no prepara ninguna entrega hacia RAG Studio); se renumeraron en
    consecuencia "6.12 Auditoría" y "6.13 Configuración", y dentro de
    esta última se agregó la subsección faltante "6.13.1 Carpeta de
    datos"; se documentaron los botones "Ocultar documentos"/"Ocultar
    estado" de la pantalla "Revisión" (sección 6.4.1) y la preparación
    automática de la entrega hacia RAG Studio al cerrar un lote desde la
    etapa 9 del Asistente (sección 5.3.9), ambos comportamientos reales
    que el Manual no mencionaba. Verificado estructuralmente (591
    párrafos, validación XSD sin errores) y visualmente, renderizando a
    PDF con LibreOffice y revisando página por página: numeración de
    listas nuevas reiniciada correctamente en 1 (requería un
    `<w:lvlOverride>` explícito por lista, no solo un `numId` propio), y
    los nuevos párrafos "Observación:"/"Importante:" con el mismo estilo
    de aviso (borde izquierdo de color, etiqueta en negrita) que el
    resto del documento.

- **Tres reportes reales de usuario (evidencia en video y consola,
  2026-09-02): "Archivar/Eliminar proyecto", corrección tras aprobar, y
  crash de RAG STUDIO.** El consultor compartió la evidencia de un
  usuario real de ambas herramientas hermanas -- video y consola para
  cada caso -- con tres hallazgos: (1) RAG_CONTENT_01, "tratamiento a
  proyecto que no proceden, ¿cómo eliminarlos?"; (2) RAG_CONTENT_02,
  la imposibilidad de editar un documento ya aprobado; (3) RAG_STUDIO_01,
  un crash real al abrir la pestaña de metadatos. Cada uno se
  diagnosticó por separado antes de decidir cómo resolverlo, en vez de
  tratar los tres como el mismo tipo de problema.
  - **RAG_CONTENT_01 -- funcionalidad real y faltante, confirmada por
    grep exhaustivo:** `EstadoProyecto` ya tenía `ARCHIVADO` definido
    desde antes (sin usar) y `ProjectRepository.list()` ya anticipaba un
    parámetro `incluir_archivados`, pero ningún caso de uso ni botón de
    la interfaz exponía archivar o eliminar un proyecto. Se preguntó al
    consultor cómo resolverlo (era una decisión de producto, no un
    hecho verificable en el código) y se respondió: agregar el estado
    "archivado" y también la eliminación real, siguiendo el mismo
    patrón que RAG STUDIO ya usa para sus propios proyectos. Se
    implementó exactamente así, replicando de RAG STUDIO tanto los
    nombres de las excepciones como su lección más importante: borrar
    la carpeta física del proyecto *antes* de borrar su fila del
    índice (nunca al revés, para no dejar datos huérfanos en disco sin
    ninguna visibilidad si el sistema de archivos falla a medio
    camino). `Proyecto.archivar()` (dominio, transición de un solo
    sentido); `ArchivarProyecto` y `EliminarProyecto` (aplicación, esta
    última bloqueada con `ProjectInUseError` si el proyecto todavía
    tiene documentos registrados, verificado contra su propio
    `proyecto.db` sin crear ese archivo solo por preguntar si existe);
    `ProjectContentChecker` (nuevo puerto, cruza al contexto Documentos
    igual que el equivalente de RAG STUDIO); botones "Archivar
    proyecto"/"Eliminar proyecto" en el panel de Proyectos, con aviso
    si el proyecto abierto en ese momento es el que se archivó o
    eliminó. 16 pruebas nuevas (3 de dominio, 9 de aplicación, 4 de
    integración de punta a punta contra el sistema de archivos real).
  - **RAG_CONTENT_02 -- diseño intencional, no un defecto: se
    documentó, no se "corrigió".** `Documento.corregir()` exige el
    estado EXTRAÍDO por diseño -- una vez aprobado, la aplicación
    genera un hash que verifica la trazabilidad del contenido exacto
    en ese momento; permitir editarlo después, incluso revirtiendo su
    estado, rompería esa garantía. El mecanismo de soporte para
    corregir un documento ya aprobado ya existía (`Vigencia.sustituye_a`
    -- volver a registrar el archivo corregido como un documento nuevo
    y vincularlo al original), pero el Manual no lo explicaba en el
    lugar donde el usuario se topa con el bloqueo. Se agregó esa
    explicación a la sección 6.4.3, junto al motivo real (hash/
    trazabilidad) para que quede claro que no es una limitación
    técnica pendiente de resolver.
  - **RAG_STUDIO_01 -- bug real en la aplicación hermana, corregido
    ahí mismo:** `MetadataPanel._fields_for_active_value_source()`
    (`ui/metadata/panel.py`) no envolvía su llamada a
    `list_applicable_fields()` en ningún `try/except`, a diferencia de
    su método hermano `_refresh_schema()`, que sí lo hacía para la
    misma excepción -- inconsistencia dentro de un mismo archivo que
    tumbaba toda la aplicación al abrir "Metadatos" > "Valores por
    fuente" en un proyecto sin esquema activo. Corregido replicando el
    mismo patrón ya usado por el método hermano. Documentado como
    Ronda 79 en el README y la bitácora de observaciones de RAG
    STUDIO.
  - Verificación: 679 pruebas en verde en este entorno (204 en
    `tests/unit/domain`, 31 en `tests/unit/app`+`scripts`+`workers`+`ui`,
    410 en `tests/unit/application`, 34 en `tests/integration`; cero
    regresiones), Ruff limpio, Mypy sin errores nuevos en ningún
    archivo tocado por esta ronda. Los 367 errores de Mypy
    preexistentes en el resto del repositorio no cambiaron ni se
    tocaron: 99 están dentro de `tests/smoke` (que no se puede
    ejecutar en este entorno de consultoría por la ya documentada
    falta de `libEGL.so.1`) y los 268 restantes están repartidos en
    otros directorios de pruebas que sí corren aquí (`tests/unit/
    domain`, `tests/unit/application`, `tests/unit/workers`,
    `tests/integration`) -- corrección de una cifra imprecisa de esta
    misma entrada, encontrada por la auditoría independiente de la
    ronda siguiente (ver bitácora del 2026-09-02 más abajo): antes
    decía que los 367 vivían todos dentro de `tests/smoke`, y no es
    así. Manual de Usuario verificado renderizando a PDF con LibreOffice e
    inspeccionando visualmente las secciones 6.1 y 6.4.3 página por
    página, y validado estructuralmente (596 párrafos, XSD sin
    errores).

- **Auditoría independiente de la ronda anterior (Archivar/Eliminar
  proyecto + fix de RAG STUDIO), 2026-09-02.** El consultor pidió una
  auditoría detallada de lo agregado en la entrada anterior de esta
  misma fecha, para detectar errores reales y corregirlos. Se lanzaron
  dos subagentes de auditoría independientes en paralelo (uno para el
  feature Archivar/Eliminar proyecto de principio a fin -- domain,
  application, infrastructure, ui, tests --, otro para el fix de RAG
  STUDIO y la consistencia de toda la documentación tocada), y cada
  hallazgo se verificó personalmente contra el código real (incluido
  corriendo Mypy/Ruff/pytest de nuevo, no solo confiando en el reporte)
  antes de aplicar ninguna corrección.
  - **Seis hallazgos reales, seis corregidos:** (1) `DuplicateProjectNameError`
    (severidad alta) bloqueaba para siempre reutilizar el nombre de un
    proyecto ya archivado -- la restricción `UNIQUE` de la base no
    distinguía por estado, contradiciendo el propio mensaje de la
    excepción ("un proyecto **activo**...") y el propósito mismo de
    archivar. Corregido con una migración nueva
    (`e567d7d3174e_quita_restriccion_unica_de_nombre_en_`, recrea la
    tabla `proyectos` sin el `UniqueConstraint` original -- SQLite no
    admite quitarlo de otra forma) más un índice no único, y
    `SqlAlchemyProjectRepository.get_by_name()` ahora filtra por
    `estado=ACTIVO`, que es exactamente lo que su único llamador
    (`CrearProyecto`) necesita. (2) `EliminarProyecto` (severidad
    medio-alta) no dejaba ningún evento en `eventos_auditoria` -- la
    única operación mutadora de todo el sistema sin ningún rastro de
    quién eliminó qué y cuándo; corregido replicando el mismo patrón
    que `ArchivarProyecto` ya usaba (el evento se registra después de
    que la carpeta y el índice se borran, y sigue siendo consultable
    porque `eventos_auditoria` vive en `aplicacion.db`, sin relación de
    llave foránea con `proyectos`). (3) Doble clic en un proyecto
    archivado desde "Proyectos recientes" del dashboard no hacía nada,
    sin ningún aviso -- el combo de la barra superior, desde el fix
    anterior, solo contiene proyectos activos, pero el dashboard seguía
    listando también los archivados; corregido filtrando el dashboard
    con el mismo criterio (`incluir_archivados=False`) en vez de
    manejar el estado inalcanzable despues. (4) Archivar o eliminar el
    proyecto que se tenía abierto avisaba con un mensaje, pero no
    soltaba `self.pctx`/`self.proyecto_actual` ni se lo comunicaba a
    los paneles -- quien cerrara el aviso seguía operando contra un
    contexto obsoleto (o, en el caso de eliminar, contra una carpeta
    que ya no existe en disco); corregido soltando el contexto y
    propagando `None` a todos los paneles de inmediato, que ya sabían
    manejar ese estado desde antes de abrir cualquier proyecto. (5)
    `tests/unit/application/test_create_project.py` seguía manteniendo
    su propia copia de `_FakeAuditLogger` en vez de importar la
    compartida de `_fakes.py`, reintroduciendo la misma duplicación que
    esa consolidación (quinta ronda de correcciones, ver bitácora)
    existe para evitar -- corregido. (6) El Manual de Usuario citaba
    entre comillas, como si fuera texto literal, una paráfrasis del
    aviso real de `ProjectInUseError` -- corregido para no presentarlo
    como cita.
  - **Documentación de RAG STUDIO, dos correcciones menores:** un
    comentario en `ui/metadata/panel.py` citaba mal el nombre del
    archivo de evidencia (`RAG_STUDIO_01/consola_RAG_STUDIO_01.txt` en
    vez de `RAG_STUDIO_01.mov`/`RAG_STUDIO_01_consola.txt`); y la
    sección "Ronda 79" de `Validacion_observaciones_RAG_STUDIO.md`
    había quedado insertada antes que "Ronda 78" en vez de después,
    rompiendo el orden ascendente que ese documento usa en todo su
    historial -- corregido reordenando las dos secciones completas sin
    perder ningún contenido (verificado con un diff de ambos archivos
    ordenados alfabéticamente, línea por línea, antes y después).
  - Nuevas pruebas de regresión, una por cada hallazgo con lógica de
    negocio verificable (los hallazgos 3, 4 y 6 son de UI/documentación,
    sin lógica nueva que ameritara una prueba aparte): dominio de la
    migración (`test_linea_global_permite_dos_proyectos_con_el_mismo_
    nombre_si_uno_esta_archivado`), dos en `test_create_project.py`
    (reutilizar nombre archivado, seguir bloqueando nombre activo
    duplicado), una en `test_archive_delete_project.py` (evento de
    auditoría al eliminar), dos de punta a punta contra SQLite real en
    `test_crear_proyecto_extremo_a_extremo.py` (auditoría que sobrevive
    al borrado, reutilización de nombre archivado). 685 pruebas en
    verde en este entorno (6 nuevas sobre las 679 de la entrada
    anterior; cero regresiones), Ruff limpio, Mypy exactamente en el
    mismo baseline de 367 errores preexistentes (diff línea por línea
    entre el reporte completo de antes y después de esta ronda: cero
    diferencias), Bandit limpio en todos los archivos tocados (1
    hallazgo Low de `B608` en la migración nueva, falso positivo -- la
    cadena interpolada es una constante de nombres de columna del mismo
    módulo, no un dato externo -- suprimido con `nosec B608` y
    justificación, mismo criterio que los demás `nosec` ya documentados
    del proyecto).

Con esto, todos los formatos de la lista confirmada (Documento Maestro,
sección 4.4) tienen ya una ruta de procesamiento real, los backends de
normalización (Módulo 9) y gestión de incidencias (Módulo 10) están
completos, el Módulo 8 (revisión contra originales) está completo --
corrección editable, verificación de fechas/cifras y navegación
sincronizada real, además de lo que ya tenía el primer prototipo --, el
Módulo 11 (Vigencias y fuentes) ya permite registrar y consultar la
fuente/vigencia de cualquier documento, el Módulo 13 (Estados y
dependencias) ya aplica sus TRES reglas de bloqueo real (incidencias
críticas abiertas, documentos críticos con vigencia desconocida, y no
liberar sin fuente/hash/aprobación), el Módulo 12 (Generador de
Markdown) ya lleva el flujo principal hasta LIBERADO, con el manifiesto
de entrega hacia RAG STUDIO listo para generarse, la Fase 6 agrega una
cola de trabajos real, con pausa, reanudación, cancelación segura,
reintentos y recuperación de trabajos huérfanos, capaz de ejecutar en
segundo plano cualquiera de esos tres casos de uso pesados, y la Fase 7
agrupa documentos en lotes y sabe cerrarlos de verdad: libera lo
aprobado, bloquea lo pendiente, y el manifiesto de entrega ya se puede
generar por lote, no solo del proyecto completo; la Fase 8 agrega los
siete documentos de la sección 7.1 (seis informes CSV más el acta de
cierre de lote en Markdown), todos recalculados en el momento a partir
de los datos ya existentes, sin ninguna tabla nueva en `proyecto.db`; la
Fase 9 corre el flujo completo de verdad sobre un corpus de documentos
reales (no sintéticos), produciendo un informe de aceptación
humano-legible contra los criterios de las secciones 8.1 y 8.2 del
Documento Maestro; y la Fase 10 agrega respaldos cifrados (Fernet) con
la clave en el almacén de credenciales del sistema operativo (`keyring`),
pruebas de restauración que reportan en vez de lanzar excepciones,
borrado seguro del zip intermedio sin cifrar, y un manual de operación
propio -- alcance acotado deliberadamente a lo estrictamente necesario
para uso personal, sin empaquetado ni actualizaciones automáticas.

- **Editor en "Normalizado" + visibilidad del ID de documento, 2026-09-04.**
  Un usuario real reportó que la herramienta funciona muy bien, y pidió
  dos mejoras puntuales a la pantalla "Revisión" (con capturas de
  pantalla como evidencia): (1) que el recuadro "Normalizado" permitiera
  acciones de edición de texto (buscar, reemplazar, números de renglón,
  ir a un renglón), sugiriendo evaluar si convenía una ventana aparte
  para no perder espacio de pantalla; (2) que se mostrara el ID de los
  documentos, porque para sustituir uno con error había que abrirlo
  fuera de la herramienta solo para conseguir su ID.
  - **Ventana aparte vs. misma ventana:** se le preguntó directamente al
    consultor cuál prefería, en vez de asumirlo -- eligió mantener todo
    en la misma ventana, con más controles para ampliarla, sobre una
    ventana independiente (que habría exigido sincronizar su contenido
    cada vez que cambia el documento o el proyecto abierto, o cerrarla a
    la fuerza si el proyecto se archiva/elimina mientras está abierta).
  - **Editor de "Normalizado" (`ui/editor_texto.py`, nuevo):** cortar,
    copiar, pegar, deshacer, rehacer y seleccionar todo ya los trae
    `QPlainTextEdit` de fábrica (Ctrl+X/C/V/Z/Y/A y menú contextual), así
    que solo se agregó lo que realmente faltaba: números de renglón (un
    gutter lateral propio, patrón estándar de Qt), buscar/reemplazar
    sobre `QTextDocument.find()` (Ctrl+F, con coincidir mayúsculas/
    minúsculas y solo palabra completa) e ir a un renglón específico
    (Ctrl+G). Se detectó y evitó a propósito un conflicto real leyendo
    el código existente: el editor NO resalta el renglón actual con
    `setExtraSelections()`, porque ese mismo mecanismo ya lo usa
    `_resaltar_baja_confianza()` para el fondo ámbar de las palabras de
    baja confianza de OCR (Nivel 1) -- como ese método reemplaza toda la
    lista de selecciones de una sola vez, resaltar también el renglón
    actual habría borrado el resaltado de baja confianza en cuanto el
    usuario hiciera clic para editar. Se agregó un tercer botón "Ocultar
    original", simétrico a los dos que ya existían ("Ocultar
    documentos"/"Ocultar estado"), para darle al editor todo el ancho
    disponible cuando hace falta corregir un tramo largo de texto.
  - **Visibilidad del ID de documento:** columna "ID" nueva en
    Inventario y en Vigencias (antes solo mostraban nombre/formato/
    estado/etc., nunca el identificador real), más un botón "Copiar ID"
    en Inventario para no tener que editar la celda a mano. En
    `RegistrarVigenciaDialog`, el campo "Sustituye a (documento_id)" pasó
    de un campo de texto vacío a un combo editable poblado con los
    documentos del proyecto (nombre e ID visibles); sigue aceptando
    pegar un ID a mano si el documento buscado no está en la lista, para
    no perder compatibilidad con el flujo anterior.
  - **Verificación:** 685 pruebas ejecutables en verde en este entorno,
    cero regresiones -- la cuenta no cambia respecto a la entrada
    anterior porque las 7 pruebas nuevas de este módulo
    (`tests/smoke/test_editor_texto.py`) viven junto a las demás pruebas
    de GUI en `tests/smoke`, que no se pueden ejecutar de verdad en este
    entorno de consultoría por la ya documentada falta de
    `libEGL.so.1`. Se verificaron en su lugar con `py_compile`, Ruff y
    Mypy, más una revisión manual línea por línea contra la API real de
    PySide6, incluida la firma exacta de `QInputDialog.getInt()`
    confirmada en los stubs del proyecto -- mismo criterio ya
    establecido para todo cambio de Qt/UI en este entorno. Ruff limpio,
    Mypy exactamente en el mismo baseline de 367 errores preexistentes
    (sin diferencias), Bandit limpio (únicos hallazgos: `assert` dentro
    de las pruebas nuevas, severidad Low, sin relevancia de seguridad).

- **Contrato de intercambio v2 con RAG STUDIO -- incidencia real de
  portabilidad Windows -> macOS, 2026-09-29.** El consultor reportó,
  con evidencia real, que un lote (`PROY-9928_licenciatura_parte_1`)
  procesado en un equipo Windows y copiado a un equipo macOS con RAG
  STUDIO se importó como "Importadas: 0 / Omitidas: 13", con los 13
  Markdown físicamente presentes en `14_entrega_rag_studio/`. Causa
  raíz confirmada con una prueba real en este mismo entorno:
  `ruta_archivo` traía la ruta absoluta completa del equipo productor
  (con backslashes de Windows), y `pathlib.Path(...).name` no la
  reconoce como tal en un sistema POSIX -- devuelve la cadena completa
  sin cambios, no solo el nombre de archivo.
  - **Diagnóstico primero, sin tocar código:** por instrucción expresa
    del consultor, se entregó primero un diagnóstico de 8 puntos (causa
    raíz con archivo/línea exactos en ambos repositorios, contrato
    actual, problemas de ese contrato, propuesta, compatibilidad,
    pruebas, riesgos de regresión, y confirmación explícita de que los
    paquetes legado podrían importarse sin editar el manifiesto a
    mano) antes de escribir una sola línea de código.
  - **Corrección del consultor a la propuesta inicial:** el consultor no
    aprobó la propuesta tal cual (nombre simple + hash solo para
    deduplicar + sin versionar), y pidió tres ajustes obligatorios antes
    de autorizar la implementación: (1) versionar el manifiesto
    (`manifest_schema_version`, ausencia = legado v1); (2) que
    `ruta_archivo` sea una referencia relativa al paquete, nunca una
    ruta absoluta del equipo productor; (3) que RAG STUDIO verifique
    `hash_contenido` contra el archivo físico como integridad
    obligatoria antes de registrar, no solo para deduplicar como hasta
    ahora -- exigiendo además que el resolutor de compatibilidad
    (basename multiplataforma) quede exclusivamente como mecanismo v1,
    nunca como el contrato normal.
  - **Documento canónico único:** `CONTRATO_INTERCAMBIO_RAG_CONTENT_STUDIO_RAG_STUDIO.md`,
    con copia idéntica en este repositorio (`DOCS PROYECTO/`) y en RAG
    STUDIO (`docs proyecto/`) -- versionado del esquema, semántica de
    columnas, algoritmo de integridad, reglas de resolución de rutas
    (V2 estricta / V1 tolerante), detección de ambigüedad entre filas,
    catálogo de mensajes de error, y 14 casos de prueba numerados
    compartidos entre ambos repositorios.
  - **Este lado (RAG Content Studio):** `_nombre_de_archivo()` en
    `application/documents/commands/generar_manifiesto.py` extrae el
    nombre de archivo reconociendo tanto `/` como `\` como separador
    (a propósito no usa `pathlib.Path(...).name`, intencionalmente
    testeable sin depender del sistema operativo donde corre la
    prueba); `FilaManifiesto.ruta_archivo` pasó a ser solo ese nombre,
    nunca una ruta absoluta; `CsvManifestWriter` agrega la columna
    `manifest_schema_version = "2"` a cada fila. El lado que verifica
    hash e interpreta rutas relativas/legado vive en RAG STUDIO (el
    consumidor); este lado solo produce el contrato v2, no lo consume.
  - **Golden package (caso 14 del contrato):** fixture idéntico
    (`tests/fixtures/golden_package_14_entrega_rag_studio/`, con copia
    exacta en RAG STUDIO) verificado de este lado en
    `tests/unit/application/test_contrato_golden_package.py` -- mismas
    columnas que produce `CsvManifestWriter` real, versión "2" en todas
    las filas, `ruta_archivo` sin separadores, y `hash_contenido`
    coincidiendo con el SHA-256 real de cada `.md` del fixture. No hay
    una sola prueba que cruce ambos repositorios/virtualenvs; el
    fixture compartido es lo que los mantiene sincronizados.
  - **Verificación:** 692 pruebas en verde (685 previas + 3 nuevas de
    `generar_manifiesto`/`csv_manifest_writer` + 5 nuevas de
    `test_contrato_golden_package.py`), cero regresiones. Ruff y Mypy
    limpios en todos los archivos tocados (Mypy: `Success: no issues
    found` en cada archivo verificado individualmente). Documento
    Maestro, sección 4.6.1, actualizado con un párrafo fechado
    2026-09-29 que corrige explícitamente la afirmación anterior de que
    "no existe todavía una vía automática" entre las dos herramientas
    (ya no era cierta desde que RAG STUDIO tiene `RegisterSourcesFromFolder`;
    el párrafo viejo había quedado desactualizado, no la implementación
    real). El lado de RAG STUDIO de esta misma corrección (resolutores
    V2/V1, verificación de hash obligatoria, 14 pruebas de contrato) se
    documenta en su propio README.

- **Hash de entrega distinto en Windows (CRLF) y auditoría de la ruta
  de intercambio, 2026-09-30.** Tras la corrección del 2026-09-29, un
  lote procesado en Windows se rechazó completo en RAG STUDIO
  ("Importadas: 0 / Omitidas: 14": "el archivo fue localizado, pero su
  contenido no coincide con el hash declarado en el manifiesto").
  - **Causa raíz (reproducida emulando el modo texto de Windows):**
    `LocalExtractionOutputStore.guardar()` usaba `write_text()`; en
    Windows cada `\n` se escribe como `\r\n`, mientras que
    `GenerarMarkdown` calculaba `hash_markdown` sobre el texto con `\n`.
    El defecto existía desde antes; se hizo visible cuando RAG STUDIO
    empezó a verificar el hash (contrato v2).
  - **Corrección:** `guardar()` escribe bytes UTF-8 exactos;
    `GenerarMarkdown` calcula el hash sobre los bytes del archivo ya
    escrito; `LocalEntregaRagStudioStore.preparar()` verifica cada
    `hash_contenido` contra la copia y, si algo no coincide o falta,
    elimina la carpeta y lanza `EntregaIntegridadError` (nueva, en
    `domain/documents/exceptions.py`); el criterio "Markdown" de
    `EjecutarPruebasDeAceptacion` comprueba el hash contra el archivo.
  - **Lotes ya generados:** `scripts/reparar_fin_de_linea_markdown.py`
    (solo biblioteca estándar; modo carpeta de entrega o modo proyecto;
    simulación por defecto, `--aplicar` para escribir con respaldo). Ver
    `MANUAL_OPERACION.md`, sección 8.
  - **Auditoría posterior (mismos riesgos en otros puntos):**
    (1) `TxtMarkdownExtractor` y `JsonExtractor` leían con `utf-8`: un
    archivo con BOM (Bloc de notas de Windows) dejaba U+FEFF al inicio
    del Markdown, de modo que el "# Titulo" inicial dejaba de ser
    encabezado, y un JSON con BOM se rechazaba como inválido; ahora leen
    con `utf-8-sig`. (2) La copia en `14_entrega_rag_studio/` se nombraba
    con `Path(ruta).name` mientras el manifiesto usaba un nombre
    multiplataforma; ambos usan ahora `domain/documents/rutas.py`.
    (3) El script de reparación se endureció: respalda una sola vez un
    archivo citado por varias filas (antes la segunda copia pisaba el
    original), no repara filas ambiguas, respeta rutas V2 con
    subcarpetas y nunca escribe fuera de la carpeta, y lee manifiestos
    con BOM. (4) En RAG STUDIO, el importador lee el manifiesto con
    `utf-8-sig` (un manifiesto guardado con Excel hacía tratar todas las
    filas como legado) y compara el hash declarado en minúsculas. El
    receptor sigue sin normalizar fines de línea.
  - **Verificación:** 714 pruebas en verde en unit + integración (692
    previas + 22 nuevas), Ruff limpio en todo el repositorio, Mypy sin
    errores en `app application domain infrastructure workers scripts`.
    Prueba cruzada con el importador real de RAG STUDIO: lote antiguo
    generado en Windows 0/3 → reparado 3/3; lote nuevo en Windows 3/3;
    proyecto antiguo: "Preparar entrega" rechazada → reparado en modo
    proyecto → entrega aceptada 3/3. Las pruebas de GUI (`tests/smoke`)
    no se ejecutaron por la ya documentada falta de `libEGL.so.1`; no se
    modificó código de UI. Contrato de intercambio (sección 6.1, copia
    idéntica en ambos proyectos) y Documento Maestro (sección 4.6.1)
    actualizados.
  - **Observación sin corregir (requiere decisión):** en la captura del
    incidente, `UDL_programa_licenciatura_artes_plasticas.pdf` aparece
    dos veces: dos documentos liberados con el mismo título en el mismo
    lote. No es un error de código, pero si uno es una versión anterior
    se entregarían ambas. Hoy nada lo advierte antes de entregar.

- **Selección de documentos al cerrar un lote + entregas separadas por
  lote con versión, 2026-10-03 (NEXOM, caso real: Proyecto AGENTE UDL,
  PROY-9625, lote LIC-01 -- 25 licenciaturas ya liberadas y entregadas,
  10 diplomados pendientes de cierre en el mismo proyecto).** Dos
  documentos del consultor dispararon esta ronda:
  `Solicitud_Ajustes_RAG_Content_Lotes_y_Portabilidad.pdf` (ajustes
  pedidos) y `Hallazgo en RAG Studio_20261002.pdf` (bug de importación
  reportado con capturas).
  - **Causa raíz del escenario real:** `EtapaCerrarLote` (Asistente,
    "Cerrar lote") no ofrecía ninguna selección -- creaba un lote con
    **todos** los documentos del proyecto y lo cerraba de inmediato. Un
    operador con licenciaturas ya cerradas y diplomados pendientes no
    tenía forma de cerrar solo los diplomados sin arrastrar (o
    reintentar sobre) las licenciaturas. Además,
    `LocalEntregaRagStudioStore.preparar()` escribía siempre en la misma
    carpeta raíz fija (`14_entrega_rag_studio/`), **borrándola por
    completo en cada corrida** -- entregar un lote nuevo podía eliminar
    sin aviso la entrega ya hecha de otro lote cerrado antes.
  - **Selección explícita al cerrar un lote (Documento Maestro, sección
    10.1, etapa 14):** nueva excepción `SeleccionLoteVaciaError`
    (`domain/batches/exceptions.py`); clasificación compartida
    `clasificar_para_cierre()` extraída a `application/batches/
    _resolucion.py` para que la vista previa y el cierre real NUNCA
    puedan divergir; consulta de solo lectura `PrevisualizarSeleccionLote`
    (`application/batches/queries/`); caso de uso compuesto
    `CrearLoteConSeleccionYCerrar` (`application/batches/commands/
    crear_lote_con_seleccion.py`) que **compone** los tres casos de uso
    ya existentes (`CrearLote` + `AgregarDocumentoALote` × N +
    `CerrarLote`) -- no se agregó ninguna regla de negocio nueva, se
    reutilizó lo existente tal como pedía el ticket. La protección ya
    existente de `AgregarDocumentoALote` (cuarta auditoría general,
    2026-08-01: rechaza reasignar un documento cuyo lote de origen ya
    está CERRADO) se mantiene intacta -- incluir sin querer un documento
    ya entregado en un lote nuevo falla con `LoteCerradoError`, nunca lo
    reasigna en silencio.
  - **UI (`EtapaCerrarLote`, Asistente, etapa 9):** la tabla de
    documentos ahora tiene una columna de selección (sin nada marcado
    por defecto -- incluir cualquier documento, ya liberado antes o no,
    es una decisión explícita del operador) más Título/ID/Estado/"Lote
    anterior"; contador de seleccionados; botón renombrado a "Crear lote
    con los documentos seleccionados y cerrarlo"; bloqueo de selección
    vacía (cliente y `SeleccionLoteVaciaError` del backend); diálogo de
    confirmación previo que muestra el nombre del lote y cuántos
    documentos seleccionados quedarían LIBERADOS/BLOQUEADOS (y por qué),
    usando `previsualizar_seleccion()` -- la misma clasificación que el
    cierre real aplica después.
  - **Entregas separadas por lote, con versión
    (`infrastructure/filesystem/entrega_rag_studio_store.py`):**
    `EntregaRagStudioStore.preparar()` ganó un parámetro opcional
    `identificador_entrega` (`None` = comportamiento de siempre, entrega
    de todo el proyecto). Con un lote, crea/reutiliza
    `14_entrega_rag_studio/<id_lote>_<slug_del_nombre>/` y escribe en una
    subcarpeta `vN` nueva (`v1`, `v2`, ...) cada vez que se (re)exporta
    ese mismo lote -- nunca sobrescribe una versión anterior ni toca la
    carpeta de otro lote. **Bug real encontrado por la propia prueba
    nueva antes de llegar a producción:** la primera versión de la rama
    "entrega de todo el proyecto" (`identificador_entrega=None`) seguía
    haciendo `shutil.rmtree()` sobre la carpeta raíz completa -- habría
    seguido borrando las subcarpetas de entrega por lote. Corregido para
    solo eliminar los archivos sueltos de la raíz, nunca subcarpetas.
  - **LotesPanel (Modo Avanzado):** nuevo botón "Exportar entrega de
    este lote..." -- reexporta la entrega de un lote ya CERRADO de forma
    independiente del cierre (crea una versión nueva, nunca otro lote),
    para el caso "el cierre fue bien pero la exportación falló por
    permisos -- reintentar sin crear otro lote" que pedía el ticket.
  - **Importación en RAG Studio y hash/CRLF del `Hallazgo en RAG
    Studio_20261002.pdf`: ya estaban resueltos antes de esta ronda**, sin
    necesidad de ningún cambio de código nuevo -- se verificó leyendo el
    código y corriendo sus pruebas, no se asumió: el `UNIQUE constraint
    failed: project_index.name` al importar sobre un proyecto existente
    ("AGENTE UDL") se corrigió en RAG Studio, Ronda 88 (2026-10-02),
    reescribiendo los ids al importar con `new_project_id`/`new_name`
    (UI → `ImportProject` → `packager.import_project()`), con 9 pruebas
    de regresión dedicadas que incluyen ese mismo nombre de proyecto; y
    el hash/CRLF se corrigió el 2026-09-30 (entrada de arriba). Ningún
    archivo de RAG Studio se tocó en esta ronda.
  - **Hallazgo real descubierto durante la verificación de esta
    ronda, no relacionado con el ticket:** las 32 pruebas de GUI real
    (`tests/smoke`, `pytest-qt`) nunca se habían podido ejecutar en este
    entorno de desarrollo por falta de `libEGL.so.1` (ver "Desviaciones
    conocidas de entorno" más abajo) -- esta vez se resolvió con
    `apt-get download` sin privilegios de root (mismo truco ya
    documentado para el Módulo 8) y se corrieron de verdad. Al hacerlo,
    tres pruebas fallaron por una causa **ajena a esta ronda**: el
    diálogo de prueba `_dialogo_vigencia_prellenado()` en
    `tests/smoke/test_gui_revision_incidencias_extremo_a_extremo.py` (×2)
    y `tests/smoke/test_gui_menu_completo_extremo_a_extremo.py` (×1)
    tenía una firma desactualizada desde que `RegistrarVigenciaDialog`
    ganó el parámetro `documentos_disponibles` (2026-09-04, Módulo 126)
    -- nunca se había detectado porque las pruebas de GUI no corrían en
    este entorno. Corregido agregando el parámetro faltante a las tres
    copias del monkeypatch; no es un error de la aplicación, solo de las
    pruebas.
  - **Verificación:** 769 pruebas en verde (692 unit + 36 integración +
    41 smoke/GUI real, corridas de verdad esta vez con `pytest-qt`
    instalado y `libEGL`/`libGL` extraídos sin root), 8 nuevas para
    `CrearLoteConSeleccionYCerrar`/`PrevisualizarSeleccionLote`
    (`tests/unit/application/test_crear_lote_con_seleccion.py`), 5
    nuevas para las entregas por lote versionadas
    (`tests/unit/application/test_entrega_rag_studio_store.py`), cero
    regresiones. Ruff y Mypy limpios (`Success: no issues found in 225
    source files`); Bandit sin hallazgos nuevos (el único hallazgo
    reportado es preexistente, en `EtapaProcesar`, línea sin tocar en
    esta ronda).

### Desviaciones conocidas de entorno (no bloqueantes)

**Tesseract (Módulo 6, ADR-001 14.1):** este entorno de desarrollo solo
tiene instalado el paquete de idioma `eng`, no `spa` — no hay acceso a
`sudo` para instalarlo desde aquí. Esto no bloquea Módulo 6: un `lang`
combinado como `spa+eng` (el valor por defecto) no falla si al menos
uno de los idiomas solicitados tiene su paquete instalado, Tesseract
simplemente ignora el que falta. Las pruebas de reconocimiento de texto
real usan `lang="eng"` explícitamente por esta razón; en la máquina de
despliegue final, con `tesseract-ocr-spa` instalado, el mismo código
reconoce español sin cambios.

**PySide6 / GUI real (`tests/smoke`, ronda de OCR 2026-08-24):** este
entorno de desarrollo puntual no tiene instalada la librería de sistema
`libEGL.so.1` que PySide6 necesita para importar `QtGui`/`QtWidgets`, y
no hay acceso a `sudo` para instalarla desde aquí -- ni siquiera
`from PySide6 import QtWidgets` a solas funciona. Esto no bloquea
ningún módulo: las 32 pruebas de `tests/smoke` (GUI real con
`pytest-qt`) simplemente no se pudieron ejecutar en esta máquina en
particular; sí corrieron, en verde, las `tests/unit/ui` (4, lógica sin
Qt real) y las `tests/integration` (30, sin GUI). En una máquina de
desarrollo con `libEGL`/`libGL` instalados (lo habitual en un entorno
de escritorio real), el mismo código y las mismas pruebas de `tests/
smoke` corren sin cambios.

**Whisper/faster-whisper (Módulo 7, ADR-001 14.1):** cargar cualquier
modelo Whisper requiere descargar sus pesos desde Hugging Face Hub la
primera vez (no vienen incluidos en el paquete de Python). El proxy de
red de este entorno de desarrollo bloquea `huggingface.co` (confirmado
con `curl`: 403 Forbidden), así que **la transcripción real no se puede
ejercitar en este entorno** — a diferencia de Tesseract, aquí no existe
ningún idioma de respaldo que evite el problema: sin pesos no hay
transcripción posible en absoluto. `FasterWhisperEngine.transcribir()`
falla con `TranscriptionEngineUnavailableError`, nunca con un crash; las
pruebas de la lógica propia del adaptador (mapeo de segmentos,
heurística de inaudible) usan un `WhisperModel` falso vía monkeypatch,
y una prueba dedicada confirma el fallo real de red tal cual ocurre.
En una máquina con acceso a Hugging Face Hub (o con los pesos ya
cacheados localmente), la transcripción funciona sin cambios de código.

**PySide6/EGL (Módulo 8, interfaz gráfica):** este entorno de
desarrollo no tiene sistema gráfico real ni las bibliotecas de sistema
`libEGL.so.1`/`libOpenGL.so.0`/`libGLX.so.0` instaladas, y no hay acceso
a `sudo`/`apt-get install` para agregarlas. `apt-get download` (a
diferencia de `apt-get install`) sí funciona sin privilegios de root, así
que se descargaron los `.deb` de `libegl1`/`libglvnd0`/`libglx0`/
`libopengl0` y se extrajeron sus `.so` (sin instalarlos en el sistema)
a un directorio propio, agregado a `LD_LIBRARY_PATH` solo para ejecutar
Qt; junto con `QT_QPA_PLATFORM=offscreen` (sin display real), esto basta
para que PySide6 arranque y las pruebas de `tests/smoke/test_gui_*.py`
corran de verdad. En la máquina de escritorio real del operador, con un
entorno gráfico normal, ninguno de estos dos ajustes es necesario.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ".[dev]"   # pytest, pytest-cov, ruff, mypy, bandit, pip-audit, pre-commit
pip install -e ".[ui]"    # solo si va a ejecutar la interfaz grafica (Modulo 8): PySide6-Essentials
```

Equivalente con `requirements*.txt` (mismo criterio que RAG STUDIO, un
archivo por grupo -- útil si su flujo de trabajo no usa los extras de
`pyproject.toml`):

```bash
pip install -e .
pip install -r requirements-dev.txt      # para correr las pruebas/calidad del nucleo
pip install -r requirements-ui.txt       # solo si va a abrir la interfaz (Modulo 8)
pip install -r requirements-ui-dev.txt   # solo si va a correr ademas las pruebas de la interfaz
```

## Ejecutar las pruebas y verificaciones de calidad

```bash
pytest tests/                 # unitarias + integracion + humo; corre con cobertura automaticamente (piso: 90%)
ruff check app application domain infrastructure workers tests migrations ui run_app.py
python -m mypy                # domain/application/infrastructure/workers/app/run_app.py/ui (desde la Fase 11.4, ver mas abajo)
python -m bandit -r app application domain infrastructure workers ui run_app.py
python -m pip_audit .         # vulnerabilidades conocidas en las dependencias declaradas
```

Tres carpetas dentro de `tests/`, con un criterio de separación que no
es solo organizativo (hallazgo real de la cuarta auditoria general,
2026-08-01): `tests/unit/` (fakes en memoria, sin tocar disco ni
SQLite real), `tests/integration/` (bootstrap()/abrir_proyecto() reales
contra SQLite y sistema de archivos reales, pero SIN PySide6/qtbot --
por ejemplo, cerrar un lote, generar un Markdown o correr las pruebas de
aceptacion de punta a punta) y `tests/smoke/` (GUI real, la unica que de
verdad requiere Qt y, en este sandbox, las bibliotecas de sistema
descritas mas abajo). `tests/integration/` naci en esta misma ronda:
esos 12 archivos vivian antes dentro de `tests/smoke/` bajo la misma
convencion de nombre `test_*_extremo_a_extremo.py` que las 6 pruebas de
GUI real, lo que llevaba a asumir que todos necesitaban entorno grafico
cuando en realidad ninguno de los 12 lo requiere -- separarlos deja
`pytest tests/unit/ tests/integration/` como un ciclo de desarrollo
rapido y completo, sin ningun gate de PySide6/EGL.

Tanto `tests/integration/` como `tests/smoke/` usan una ruta temporal
(`/tmp/rag_content_studio_*`), nunca la ruta raíz real de datos
(`/media/disco/Data/RAG CONTENT STUDIO/`) — no escriben sobre proyectos
reales.

### Interfaz gráfica (Módulo 8)

```bash
pip install -e ".[ui]"        # o: pip install -r requirements-ui.txt
python run_app.py             # forma recomendada -- ver mas abajo
python -m ui                  # equivalente, delega en el mismo ui.app.main()
```

`run_app.py` (raíz del repo) es la forma recomendada de arrancar la
aplicación -- mismo patrón que `RAG STUDIO/run_app.py`. `python -m ui`
sigue funcionando como alias (`ui/__main__.py` es un delegado delgado
que importa y llama a `ui.app.main()`, la implementación real);
ninguno de los dos requiere haber instalado el paquete en modo editable
primero, aunque `pip install -e ".[ui]"` es lo más simple.

Al arrancar, `ui/app.py::main()` sigue la misma secuencia ya usada y
probada en RAG STUDIO (`ui/app.py::main`, revisado deliberadamente
antes de construir esta versión):

1. Muestra la pantalla de bienvenida con el logo del proyecto
   (`ui/splash.py`, `ui/LOGO.png`) mientras `app.bootstrap.bootstrap()`
   corre las migraciones y arma el contexto. Si `ui/LOGO.png` no existe
   o no se puede leer, la pantalla de bienvenida simplemente se omite:
   nunca es un requisito para abrir la aplicación.
2. Muestra la ventana principal en su tamaño normal y, con un breve
   retraso (`ui.app.RETRASO_MAXIMIZADO_MS`, 300 ms, ver su docstring),
   la maximiza y recién ahí cierra el splash. El retraso no es
   cosmético: pedir el maximizado en la misma ráfaga síncrona de
   arranque (antes o justo después del primer `show()`) deja la
   ventana con `isMaximized()=True` pero con la geometría del tamaño
   natural de la ventana, no la de la pantalla, bajo Mutter/XWayland --
   el compositor necesita una vuelta real del *event loop en
   ejecución* para completar el intercambio de protocolo de
   maximizado. Mismo hallazgo, mismo arreglo que RAG STUDIO.

Para correr también sus pruebas (`tests/smoke/test_gui_*.py`,
`tests/smoke/test_splash.py`, `tests/smoke/test_app_entrypoint.py`):

```bash
pip install -e ".[ui,ui-dev]"  # o: pip install -r requirements-ui.txt -r requirements-ui-dev.txt
pytest tests/smoke/test_gui_revision_incidencias_extremo_a_extremo.py tests/smoke/test_splash.py tests/smoke/test_app_entrypoint.py
```

`tests/smoke/test_app_entrypoint.py` prueba el maximizado diferido de
forma aislada (`ui.app.arrancar_ventana_maximizada()`, extraída de
`main()` justo para esto) con `qtbot`, sin instanciar un `QApplication`
propio -- `ui.app.main()` construye el suyo (`QApplication(sys.argv)`),
lo cual chocaría con el que ya provee `pytest-qt` para toda la sesión
de pruebas.

Desde la Fase 11.4, `ui` está dentro del `files` de Mypy en
`pyproject.toml` igual que el resto del código (Ruff y Bandit ya lo
cubrían desde la Fase 11). Los huecos reales en los stubs de PySide6
(por ejemplo, `QDialogButtonBox.Ok`/`.Cancel` o
`QHeaderView.Stretch`, que sí existen en tiempo de ejecución pero los
stubs solo reconocen en su forma anidada `.StandardButton.Ok`/
`.ResizeMode.Stretch`) se resolvieron usando esa forma anidada, sin
`# type: ignore` -- verificado que ambas formas funcionan igual en
tiempo de ejecución antes de cambiar el código. La única excepción real
es `ui/pdf_preview.py::render_pagina` (`QPixmap.loadFromData` con `str`
en vez de `bytes`, ver su comentario), con un `# type: ignore` puntual
porque el comportamiento correcto en tiempo de ejecución para esta
versión de PySide6/shiboken es justamente el que el stub no contempla.
`ui.main_window.MainWindow` usa un `typing.Protocol`
(`_PanelConProyecto`) para tipar los paneles heterogéneos que
implementan `establecer_proyecto(pctx, proyecto)` sin compartir una
clase base propia más allá de `QWidget`. El antiguo
`[[tool.mypy.overrides]]` de `ui.*` con `follow_imports = "skip"` (que
existía para que `run_app.py` no arrastrara los huecos de stubs de
antes) se retiró: quedó redundante en cuanto `ui` pasó a estar
explícito en `files` (confirmado corriendo Mypy con y sin el override:
0 errores en ambos casos).

### Automatizar todo lo anterior en cada commit (pre-commit)

Requiere que este directorio sea un repositorio git (`git init`, una
sola vez, hecho por quien clona el proyecto — no se pudo inicializar
desde este entorno de trabajo por una limitación del conector, no del
proyecto en sí).

```bash
git init                 # si el repositorio todavia no existe
pip install -e ".[dev]"
pre-commit install       # instala el hook; a partir de aqui corre solo en cada commit
```

El hook (`.pre-commit-config.yaml`) ejecuta Ruff, Mypy, Bandit y Pytest
en ese orden — un commit que rompa cualquiera de los cuatro se
rechaza automáticamente (Documento Maestro, sección 4.11.1: principios
de baja fricción).

## Estructura

Ver ADR-001 (`DOCS PROYECTO/RAG_Content_Studio_Desktop_ADR-001_...docx`),
secciones 3 a 9, para la vista de capas, el modelo de dominio y la
estructura de directorios completa. Resumen de lo ya implementado:

- `domain/projects/` — entidad `Proyecto`, puertos (`ProjectRepository`,
  `ProjectFileStore`, `AuditLogger`), excepciones.
- `domain/profiles/` — entidad `PerfilProyecto` (con `CampoMetadato`,
  `Catalogo`, `EntradaCatalogo`, `ReglaValidacion`, `TipoDato`), puerto
  `ProfileRepository`, excepciones (`ProfileVersionAlreadyExistsError`,
  `ProfileNotFoundError`).
- `domain/documents/` — entidad `Documento` (con `Prioridad`,
  `Criticidad`, `TipoProcesamiento`, `FormatoDocumento`,
  `EstadoDocumento`/flujo principal y las reglas de transición
  `Documento.avanzar_a()`/`Documento.clasificar()`/
  `Documento.completar_extraccion()`/`Documento.corregir()` (Módulo 8)/
  `Documento.completar_normalizacion()`/`Documento.aprobar_para_markdown()`/
  `Documento.generar_markdown()`/`Documento.validar_markdown()`/
  `Documento.liberar()` (Módulo 12, 2026-07-28), más
  `Documento.mapa_paginas` y `Documento.ruta_revisado` (Módulo 8) y el
  helper `Documento.ruta_markdown_vigente()`), `ResultadoExtraccion`
  (incluye `mapa_paginas`), `Segmento`/`ResultadoTranscripcion` (Módulo
  7), `ResultadoNormalizacion` (Módulo 9), `Revision` (Módulo 8,
  historial de revisiones humanas), `Aprobacion` (Módulo 12, historial
  de aprobaciones para generar Markdown, mismo principio que
  `Revision`), `FilaManifiesto` (Módulo 12, un renglón del manifiesto de
  entrega hacia RAG STUDIO), `verificacion_fechas_cifras.py`
  (`detectar_fechas_y_cifras()`, Módulo 8: funcion pura de deteccion,
  no de validacion), `estructura_markdown.py`
  (`tiene_estructura_markdown()`, Módulo 12: funcion pura que detecta
  encabezados/tablas Markdown reales), puertos (`DocumentRepository`,
  `OriginalFileStore`, `PdfTextLayerDetector`, `DocumentExtractor`,
  `ExtractionOutputStore`, `OcrEngine`, `LegacyFormatConverter`,
  `TranscriptionEngine`, `NormalizationEngine`, `RevisionRepository`,
  `AprobacionRepository`, `ManifestWriter`), excepciones (incluye
  `CorreccionRequiereEstadoExtraidoError`, `MarkdownVacioError`).
- `domain/profiles/` (ampliado, Módulo 9) — `ReglaNormalizacion`
  (parámetros de texto libre, sin tipos de dominio en el YAML, mismo
  criterio que `ReglaValidacion`) y `PerfilProyecto.reglas_normalizacion`.
- `domain/incidents/` (Módulo 10) — entidad `Incidencia` (con
  `EtapaIncidencia`, `SeveridadIncidencia`, `EstadoIncidencia` y los
  métodos de transición `asignar()`/`responder()`/`decidir()`/
  `cerrar()`/`esta_abierta()`), función pura `filtrar_criticas_abiertas()`
  (Módulo 13), puerto `IncidentRepository`, excepciones
  (`InvalidIncidentStateTransitionError`, `IncidentNotFoundError`). No
  importa `domain.documents`.
- `domain/governance/` (Módulo 13, nombre de paquete ya previsto en el
  ADR-001 sección 7) — excepciones `IncidenciasCriticasAbiertasError`,
  `VigenciaDesconocidaError`, `FuenteFaltanteError` y
  `AprobacionFaltanteError` (2026-07-28, tercera regla). No importa
  `domain.incidents`/`domain.documents`/`domain.validity`; todo cruce
  real se resuelve en `application.governance` (mismo principio de
  aislamiento que esos contextos ya guardan entre sí).
- `domain/validity/` (Módulo 11) — entidades `Fuente` y `Vigencia`
  (independientes, ver ADR-001 sección 5: "no deben confundirse"),
  funcion pura `vigencia_desconocida()`, puertos `FuenteRepository`/
  `VigenciaRepository` (`get_by_document`/`save`, sin `id` sintetico:
  a lo sumo un registro por documento). No importa `domain.documents`.
- `domain/audit/` — entidad `EventoAuditoria`.
- `domain/jobs/` (Fase 6, 2026-07-28) — entidad `Trabajo` (siete estados
  exactos de ADR-001 sección 10: `pendiente`, `preparando`,
  `ejecutando`, `pausado`, `completado`, `fallido`, `cancelado`; máquina
  de transiciones propia — `ejecutando` no admite pausa ni cancelación,
  ver su docstring), `TipoTrabajo` (`extraccion`, `normalizacion`,
  `generacion_markdown`), `Prioridad` propia (no reutiliza la de
  `domain.documents`: aislamiento entre dominios), función pura
  `orden_prioridad()`, puerto `TrabajoRepository`. No importa
  `domain.documents` en absoluto.
- `domain/batches/` (Fase 7, 2026-07-28) — entidad `Lote` (dos estados,
  `ABIERTO`/`CERRADO`; `CERRADO` es terminal), puerto `LoteRepository`.
  No importa `domain.documents` en absoluto -- la relación con
  `Documento` vive del lado de `Documento.lote_id` (nuevo campo en
  `domain.documents.entities`, con los metodos `asignar_a_lote()`/
  `quitar_de_lote()`, que no tocan `estado`).
- `domain/reports/` (Fase 8, 2026-07-29) — value objects puros por cada
  documento de la sección 7.1 (`FilaInventario`, `FilaProcesamiento`,
  `FilaRevision`, `FilaIncidencia`, `FilaCalidad`, `FilaTrazabilidad`,
  `ActaCierreLote`) y puerto `ReportWriter` (agrupa los siete métodos de
  escritura, mismo criterio que `DocumentRepository` agrupando varias
  operaciones en un solo puerto). No importa ningún otro `domain.*`.
- `domain/acceptance/` (Fase 9, 2026-07-29) — value objects
  `CriterioDominio`, `CriterioUmbral`, `InformeAceptacion` (con
  `aprobado()`/`esta_completo()`, las únicas dos consultas con lógica
  real de este contexto) y puerto `InformeAceptacionWriter`. No importa
  ningún otro `domain.*`.
- `domain/security/` (Fase 10, 2026-07-29) — value objects
  `RespaldoProyecto`/`RestauracionRespaldo` y puertos `CredentialStore`
  (un secreto por nombre) y `RespaldoStore` (crear/restaurar un respaldo
  cifrado, mismo criterio de granularidad que `ReportWriter`). No
  duplica `NivelConfidencialidad` (ya existe en `domain.projects` desde
  la Fase 1) ni importa ningún otro `domain.*`.
- `application/projects/` — caso de uso `CrearProyecto` y su fachada
  `ProjectsService`.
- `application/profiles/` — casos de uso `CrearPerfil`,
  `PublicarNuevaVersionPerfil`, `CompararVersionesPerfil` y su fachada
  `ProfilesService`.
- `application/documents/` — casos de uso `RegistrarDocumento`,
  `ClasificarDocumento`, `ExtraerDocumento`, `CorregirExtraccion`
  (Módulo 8, guarda `ruta_revisado` sin avanzar de estado),
  `NormalizarDocumento` (Módulo 9, lee `ruta_markdown_vigente()`),
  `RevisarDocumento` (Módulo 8, `EXTRAIDO -> EN_REVISION -> REVISADO`),
  `AprobarParaMarkdown` (Módulo 12, `NORMALIZADO ->
  PENDIENTE_DE_APROBACION -> APROBADO_PARA_MARKDOWN`, guarda
  `Aprobacion` y reutiliza la verificación de `GovernanceService`),
  `GenerarMarkdown` (Módulo 12, copia hacia `07_markdown/` y calcula
  `hash_markdown`), `ValidarMarkdown` (Módulo 12, rechaza Markdown vacío
  y registra advertencias no bloqueantes de estructura) y
  `LiberarDocumento` (Módulo 12/13, `VALIDADO -> LIBERADO`, verificado
  por `GovernanceService.verificar_documento_liberable()`) más
  `GenerarManifiesto` (Módulo 12, arma el manifiesto de entrega hacia
  RAG STUDIO a partir de los documentos `LIBERADO` del proyecto), y su
  fachada `DocumentsService`.
- `application/incidents/` (Módulo 10) — casos de uso
  `RegistrarIncidencia`, `AsignarIncidencia`, `ResponderIncidencia`,
  `DecidirIncidencia` y `CerrarIncidencia`, y su fachada
  `IncidentsService` (incluye `existen_criticas_abiertas()`, consulta
  de solo lectura; el bloqueo real ya lo aplica `application.governance`).
- `application/governance/` (Módulo 13) — casos de uso
  `VerificarDocumentoAprobable` (depende directamente de
  `IncidentRepository`, `VigenciaRepository` y `DocumentRepository`, no
  de sus fachadas de aplicación — mismo patrón que
  `RegistrarIncidencia`; reutilizado tanto por `RevisarDocumento` como
  por `AprobarParaMarkdown`) y `VerificarDocumentoLiberable` (nuevo,
  2026-07-28, depende de `FuenteRepository`/`AprobacionRepository`,
  usado por `LiberarDocumento`), y su fachada `GovernanceService`. Tres
  reglas completas: incidencias críticas abiertas, documentos críticos
  con vigencia desconocida, y no liberar contenido sin fuente y
  aprobación (sección 4.7).
- `application/validity/` (Módulo 11) — casos de uso `RegistrarFuente`/
  `RegistrarVigencia` (upsert, validan `documento_id`/`sustituye_a`
  contra `DocumentRepository` — mismo patrón que `RegistrarIncidencia`)
  y su fachada `ValidityService` (incluye `obtener_fuente()`/
  `obtener_vigencia()`, consultas de solo lectura).
- `application/jobs/` (Fase 6) — `EncolarTrabajo` (valida el documento
  contra `DocumentRepository`, mismo patrón que `RegistrarIncidencia`),
  `IniciarPreparacion`, `IniciarEjecucion`, `CompletarTrabajo`,
  `FallarTrabajo`, `PausarTrabajo`, `ReanudarTrabajo`, `CancelarTrabajo`,
  `ReintentarTrabajo` (bloqueado por `ReintentosAgotadosError` si ya se
  agotó `max_intentos`) y `RecuperarTrabajosInterrumpidos` (marca
  `fallido`, con mensaje explícito, cualquier trabajo huérfano en
  `preparando`/`ejecutando` — se invoca una sola vez, automáticamente,
  al abrir un proyecto), y su fachada `JobsService`.
- `application/batches/` (Fase 7) — `CrearLote`, `AgregarDocumentoALote`/
  `QuitarDocumentoDeLote` (validan lote `ABIERTO` y documento existente,
  mismo patrón que `EncolarTrabajo`) y `CerrarLote` (libera lo `VALIDADO`
  reutilizando `GovernanceService.verificar_documento_liberable()` --
  nunca instancia el `LiberarDocumento` completo de otro contexto, para
  no acoplar `application.batches` a como se construye
  `application.documents` --, bloquea el resto, y cierra el propio
  `Lote`), y su fachada `BatchesService`.
- `application/reports/` (Fase 8) — `GenerarInformeInventario`,
  `GenerarInformeProcesamiento` (cruza `DocumentRepository`/
  `TrabajoRepository`), `GenerarInformeRevision`,
  `GenerarInformeIncidencias`, `GenerarInformeCalidad` (reutiliza
  `GovernanceService.verificar_documento_liberable()`, nunca duplica la
  regla), `GenerarInformeTrazabilidad` y `GenerarActaCierreLote`
  (exige un `Lote` ya `CERRADO`, separado a propósito de `CerrarLote`),
  y su fachada `ReportsService` (incluye
  `generar_todos_los_informes()`).
- `application/acceptance/` (Fase 9) — `EjecutarPruebasDeAceptacion`,
  el único caso de uso de este contexto: depende directamente de las
  FACHADAS de aplicación (`DocumentsService`/`ValidityService`/
  `IncidentsService`/`BatchesService`/`ReportsService`), no de puertos
  de domain -- a diferencia del resto del código, orquesta el flujo
  completo que un operador real ejecutaría a mano, igual que lo haría
  `ui`. Su fachada `AcceptanceService` expone
  `ejecutar_pruebas_de_aceptacion(corpus_dir)`.
- `application/security/` (Fase 10) — `CrearRespaldo` (reutiliza la
  clave existente del proyecto o genera una nueva la primera vez) y
  `RestaurarRespaldo` (lanza `ClaveDeRespaldoNoEncontradaError` solo si
  no hay NINGUNA clave guardada; una clave incorrecta o un archivo
  corrupto se reporta, no se lanza). Su fachada `SecurityService` expone
  `crear_respaldo(proyecto_id, carpeta_proyecto)`/
  `restaurar_respaldo(proyecto_id, ruta_archivo, destino)`.
- `infrastructure/database/` — modelos SQLAlchemy para la base global
  (`models.py`) y para la base por proyecto (`project_models.py`, en un
  `DeclarativeBase` separado a propósito — ver su docstring), `types.py`
  (`UTCDateTime`, un `TypeDecorator` que evita que SQLite descarte el
  `tzinfo` de los timestamps al leerlos de vuelta — ver su docstring),
  motor SQLite en modo WAL reutilizable para ambas bases (`engine.py`),
  adaptadores `SqlAlchemyProjectRepository`/`SqlAlchemyAuditLogger`/
  `SqlAlchemyDocumentRepository`/`SqlAlchemyIncidentRepository`
  (Módulo 10, tabla `incidencias` propia dentro de `proyecto.db`)/
  `SqlAlchemyRevisionRepository` (Módulo 8, tabla `revisiones` propia,
  registros inmutables — `save()` siempre inserta, nunca actualiza)/
  `SqlAlchemyFuenteRepository`/`SqlAlchemyVigenciaRepository` (Módulo
  11, tablas `fuentes`/`vigencias`, clave primaria `documento_id`
  directa)/`SqlAlchemyAprobacionRepository` (Módulo 12, tabla
  `aprobaciones` propia, registros inmutables como `revisiones`)/
  `SqlAlchemyTrabajoRepository` (Fase 6, tabla `trabajos` propia,
  upsert como `documentos` — un `Trabajo` muta a lo largo de su propio
  ciclo de vida; `list_pendientes_por_prioridad()` ordena en Python con
  la función pura `domain.jobs.entities.orden_prioridad()`, nunca
  duplicada como una expresión CASE en SQL)/`SqlAlchemyLoteRepository`
  (Fase 7, tabla `lotes` propia, más la columna `lote_id` nueva en
  `documentos`), y `migrations.py` (`upgrade_to_head()`, API
  programática de Alembic — ver más abajo).
- `infrastructure/extraction/` — `PyPdfTextLayerDetector` (Módulo 4);
  `CompositeDocumentExtractor` (Módulos 5-7 + DOC/XLS legado) y sus
  adaptadores por formato/ruta (`TxtMarkdownExtractor`, `JsonExtractor`,
  `DocxExtractor`, `PdfExtractor`, `XlsxExtractor`, `CsvExtractor` para
  extracción directa; `ImageOcrExtractor`, `PdfOcrExtractor` para OCR,
  Módulo 6; `DocLegacyExtractor`, `XlsLegacyExtractor` para DOC/XLS;
  `AudioVideoTranscriptionExtractor` para transcripción, Módulo 7) más
  `markdown_helpers.py` (`repair_letter_spaced_text`,
  `rows_to_markdown_table`), `tesseract_ocr_engine.py`
  (`TesseractOcrEngine`, adaptador de `domain.documents.ports.OcrEngine`
  vía `pytesseract`), `libreoffice_converter.py`
  (`LibreOfficeConverter`, adaptador de
  `domain.documents.ports.LegacyFormatConverter` vía `soffice
  --headless`) y `faster_whisper_engine.py` (`FasterWhisperEngine`,
  adaptador de `domain.documents.ports.TranscriptionEngine` vía
  `faster-whisper`) — adaptados de RAG STUDIO como código propio (salvo
  la conversión legado y la transcripción, propias de esta herramienta:
  RAG STUDIO no maneja ninguna de las dos), no importados en vivo
  (ADR-001, sección 8).
- `infrastructure/normalization/` — `RuleBasedNormalizationEngine`
  (Módulo 9, adaptador de `domain.documents.ports.NormalizationEngine`)
  — motor propio de RAG Content Studio Desktop, sin dependencias
  externas ni de red (RAG STUDIO no tiene este adaptador: no normaliza
  Markdown ya extraído).
- `infrastructure/filesystem/` — `LocalProjectFileStore` (estructura de
  13 subcarpetas + `proyecto.yaml`), `YamlProfileRepository` (paquetes
  de perfil versionados e inmutables), `LocalOriginalFileStore` (copia
  inmutable + hash SHA-256 hacia `01_originales/`),
  `LocalExtractionOutputStore` (Markdown hacia `03_extracciones/`,
  `04_transcripciones/`, `05_revisiones/` (Módulo 8, correcciones),
  `06_normalizados/` o `07_markdown/` (Módulo 12, entrega final) según
  el store con el que se construya cada instancia), y
  `csv_manifest_writer.py` (`CsvManifestWriter`, adaptador de
  `domain.documents.ports.ManifestWriter` — Módulo 12, escribe siempre
  el mismo archivo `12_exportaciones/manifiesto.csv`, sobrescribiendo) y
  `local_report_writer.py` (`LocalReportWriter`, Fase 8, adaptador de
  `domain.reports.ports.ReportWriter` — escribe los seis informes CSV
  hacia `10_reportes/`, sobrescribiendo cada uno, y el acta de cierre de
  lote en Markdown, un archivo por lote) y
  `markdown_informe_aceptacion_writer.py`
  (`MarkdownInformeAceptacionWriter`, Fase 9, adaptador de
  `domain.acceptance.ports.InformeAceptacionWriter` — a diferencia de
  los dos anteriores, cada corrida queda archivada por separado, nunca
  se sobrescribe).
- `infrastructure/security/` (Fase 10, 2026-07-29) —
  `keyring_credential_store.py` (`KeyringCredentialStore`, adaptador de
  `domain.security.ports.CredentialStore` sobre `keyring`; el backend
  real lo elige `keyring` según el sistema operativo, este adaptador no
  sabe cuál es) y `encrypted_zip_respaldo_store.py`
  (`EncryptedZipRespaldoStore`, adaptador de `RespaldoStore`: empaqueta
  con `zipfile`, cifra con Fernet (`cryptography`), verifica "zip slip"
  antes de restaurar, y borra de forma segura el zip intermedio sin
  cifrar sobrescribiéndolo con bytes aleatorios).
- `scripts/` (Fase 9, 2026-07-29) — `ejecutar_pruebas_aceptacion.py`:
  punto de entrada manual que arma un proyecto nuevo sobre una raíz
  aislada propia (`corpus_aceptacion/_runtime/`, nunca la ruta raíz real
  de datos) y corre `AcceptanceService` contra
  `corpus_aceptacion/documentos/`. Desde la Fase 10, también
  `gestionar_respaldos.py` (`listar`/`crear`/`restaurar`), que sí opera
  sobre la ruta raíz real -- ver `MANUAL_OPERACION.md`. Desde el
  2026-09-30, `reparar_fin_de_linea_markdown.py` (repara lotes de
  entrega generados en Windows con versiones anteriores; solo biblioteca
  estándar -- ver `MANUAL_OPERACION.md`, sección 8).
- `app/` — `configuration.py` (ruta raíz única confirmada) y
  `bootstrap.py` (ensamblado de dependencias: `bootstrap()` para la
  base global y `abrir_proyecto()` para la base de un proyecto
  específico; ambos aplican las migraciones de Alembic antes de abrir
  la sesión). Desde la Fase 6, `abrir_proyecto()` también ensambla
  `JobsService`/`ColaDeTrabajos` y llama a
  `recuperar_trabajos_interrumpidos()` una sola vez, antes de exponer
  el `ProjectContext` (mismo principio que aplicar las migraciones: "el
  operador nunca lo ejecuta a mano"). Desde la corrección del
  2026-07-29 (documentos atascados en "en_extraccion"/
  "en_normalizacion"), también llama a
  `documents.recuperar_documentos_interrumpidos()` justo después de
  ensamblar `DocumentsService`, mismo principio y mismo lugar. Desde la
  Fase 7, también ensambla
  `BatchesService`; desde la Fase 8, también ensambla `ReportsService`
  (sin migración propia: no agrega ninguna tabla nueva). Desde la Fase
  10, también ensambla `SecurityService` (`KeyringCredentialStore` +
  `EncryptedZipRespaldoStore`) -- sin ninguna tabla ni sesión propia: no
  depende de `proyecto.db` en absoluto, solo de la carpeta del proyecto
  en disco y del almacén de credenciales del sistema operativo.
- `workers/` (Fase 6, 2026-07-28; antes vacío) — `cola_de_trabajos.py`
  (`ColaDeTrabajos`, unico modulo de esta capa: depende de
  `application`/`infrastructure`, nunca de `ui`, ADR-001 sección 4).
  Modo síncrono determinista (`procesar_siguiente()`/
  `procesar_todos_los_pendientes()`, el que usan las pruebas) y modo en
  segundo plano real (`iniciar()`/`detener()`, `ThreadPoolExecutor`
  acotado a `max_trabajos_concurrentes` — el control de recursos
  realmente verificable en un escritorio personal sin cgroups, sección
  4.8). `_EJECUTORES` es el único punto del código que conecta
  `TipoTrabajo` con el método real de `DocumentsService` que invoca.
- `perfiles/perfil_generico/0.1.yaml` — primer perfil de prueba (Anexo B
  del Documento Maestro), ya en su formato versionado definitivo.
- `ui/` (Módulo 8, completo, PySide6) — `app.py` (`main()`,
  implementación real del arranque: splash -> `app.bootstrap.bootstrap()`
  -> ventana principal maximizada tras un breve retraso diferido, ver
  la sección de arriba; `arrancar_ventana_maximizada()` extraída aparte
  para poder probarse con `qtbot`), `main_window.py` (`MainWindow`,
  llama a `app.bootstrap.abrir_proyecto()` al abrir un proyecto),
  `dialogs.py` (`RevisarDocumentoDialog`, `RegistrarIncidenciaDialog`,
  `RegistrarVigenciaDialog` -- Módulo 11, un solo dialogo para Fuente y
  Vigencia, se prellena si ya existe un registro),
  `pdf_preview.py` (renderiza paginas de PDF a `QPixmap` via PyMuPDF —
  la unica pieza de `ui` que toca una biblioteca de terceros
  directamente), `splash.py` (pantalla de bienvenida con `LOGO.png`,
  mismo patrón que RAG STUDIO), `__main__.py` (delegado delgado de
  `ui.app.main()`, solo aplica el ajuste de Wayland antes de importar
  PySide6 -- ver `run_app.py` en la raíz del repo, la forma
  recomendada de arrancar). Ya previsto como paquete de nivel superior
  desde el ADR-001 original (sección 7) y en `pyproject.toml`
  (`packages.find`). Desde la Fase 11, Ruff es obligatorio sobre este
  paquete (tabla 8.3); desde la Fase 11.4, también Mypy estricto (ver
  más abajo, "Calidad de código").
- `ui/panels/` (Fase 11, 2026-07-29, 11 pantallas) — una clase
  `QWidget` por área del menú funcional (`ProyectosPanel`,
  `InventarioPanel`, `ProcesamientoPanel`, `NormalizacionPanel`,
  `IncidenciasPanel`, `VigenciasPanel`, `MarkdownPanel`, `PruebasPanel`,
  `ReportesPanel`, `AuditoriaPanel`, `ConfiguracionPanel`); la página de
  Revisión sigue viviendo en `main_window.py` (Módulo 8, sin cambios).
  Cada panel recibe `establecer_proyecto(pctx, proyecto)` al abrir un
  proyecto y al cambiar de página, para no mostrar datos obsoletos; solo
  depende de `app.bootstrap` (nunca construye adaptadores de
  `infrastructure` directamente, ADR-001 sección 4). Las pantallas que
  encadenan varias acciones sobre el mismo elemento seleccionado
  (Procesamiento, Incidencias, Markdown, Normalización) preservan la
  selección de la tabla a través de cada recargue -- un bug real
  encontrado por las pruebas de humo de esta fase (ver más arriba).
- `ui/wizard/` (Fase 11.2, 2026-07-29) — `AsistenteWidget`
  (`asistente_widget.py`, el contenedor: lista de etapas + navegación +
  autoguardado), `etapas.py` (siete etapas dedicadas: crear
  proyecto+perfil, procesar, revisar, normalizar, aprobar, generar
  Markdown, cerrar lote -- las otras tres etapas son paneles de
  `ui.panels.*` reutilizados sin cambios, ver más arriba) y
  `estado_asistente.py` (autoguardado de la etapa actual en
  `.asistente_estado.json`, dentro de la carpeta del proyecto).
- `ui/dashboard/` (Fase 11.3, 2026-07-29) — `PantallaPrincipalWidget`
  (`pantalla_principal_widget.py`): la vista de entrada de la ventana,
  con los ocho campos de la sección 4.11. Sin lógica propia más allá de
  agregación y presentación -- todos los datos vienen de servicios de
  `application/*` ya existentes.
- `run_app.py` (raíz del repo) — punto de entrada recomendado
  (`python run_app.py`), mismo patrón que `RAG STUDIO/run_app.py`:
  aplica el ajuste de Wayland y delega en `ui.app.main()`. Dentro de
  Mypy estricto igual que `ui/` (Fase 11.4).

## Migraciones (Alembic)

Dos líneas independientes (ADR-001, sección 9), cada una con su propio
`env.py`, `script.py.mako` y carpeta de versiones bajo `migrations/`:

- `migrations/global/` — versiona `infrastructure.database.models.Base`
  (`aplicacion.db`: proyectos, eventos de auditoría).
- `migrations/project/` — versiona
  `infrastructure.database.project_models.BaseProyecto` (`proyecto.db`:
  documentos — una base distinta por cada proyecto).

El operador nunca ejecuta Alembic a mano: `app.bootstrap.bootstrap()` y
`app.bootstrap.abrir_proyecto()` llaman
`infrastructure.database.migrations.upgrade_to_head()` automáticamente
al abrir cada base. Los comandos de Alembic por CLI (`alembic -c
alembic_global.ini revision --autogenerate -m "..."`, con
`alembic_project.ini` para la otra línea) son solo para cuando un
desarrollador necesite generar una migración nueva tras cambiar un
modelo.

## Calidad de código

Ruff, Mypy, Bandit (seguridad estática), pip-audit (vulnerabilidades de
dependencias) y Pytest con cobertura obligatoria (`pytest-cov`, piso
90%) — ver `pyproject.toml`. `.pre-commit-config.yaml` los encadena en
un solo hook (ver sección de instalación más arriba).

## Desviación conocida (no bloqueante)

El ADR-001 (sección 9) describe la auditoría como parte de `proyecto.db`;
por consistencia con el Módulo 1 ya construido y probado, el registro de
auditoría de los Módulos 1-7, 9 y 10 sigue escribiendo en la base global
(`aplicacion.db`, filtrable por `proyecto_id`). Documentado en
`app/bootstrap.py::abrir_proyecto` — pendiente de revisar cuando se
construya el contexto de gobierno/auditoría más adelante.

## Dependencia de sistema operativo: LibreOffice

La conversión de DOC/XLS legado requiere el binario `soffice`
(LibreOffice) instalado en el sistema operativo — no es una biblioteca
de Python, así que no aparece en `pyproject.toml`. Sin él,
`LibreOfficeConverter` falla con `LegacyConversionFailedError` (no un
crash) al intentar extraer un documento DOC/XLS; el resto de la
aplicación no se ve afectado.

## Próximos pasos

Con los Módulos 1-7 completos, todos los formatos de entrada de la
lista confirmada (Documento Maestro, sección 4.4) ya tienen una ruta de
procesamiento real (extracción directa, OCR, conversión legado o
transcripción); con el Módulo 9 completo el Markdown revisado ya se
puede normalizar con reglas propias del perfil; con el Módulo 10
completo cualquier documento puede tener incidencias registradas,
asignadas, respondidas, decididas y cerradas, con el dato de
"¿tiene críticas abiertas?" ya consultable; con el Módulo 8 completo
(ver más arriba) la ventana principal aprueba revisiones
(`EXTRAIDO -> EN_REVISION -> REVISADO`), registra incidencias, permite
corregir el Markdown extraído, detecta fechas/cifras a verificar y
sincroniza la navegación página<->sección para PDF; con el Módulo 11
completo (ver más arriba) cualquier documento puede tener su Fuente y
su Vigencia registradas y consultables; con el Módulo 12 completo (ver
más arriba) el flujo principal ya llega hasta LIBERADO y el manifiesto
de entrega hacia RAG STUDIO se puede generar; con la Fase 6 completa
(ver más arriba) cualquiera de esos tres casos de uso pesados
(extracción, normalización, generación de Markdown) puede encolarse y
ejecutarse en segundo plano, con pausa, reanudación, cancelación
segura, reintentos y recuperación automática de trabajos huérfanos; con
la Fase 7 completa (ver más arriba) los documentos se agrupan en lotes
y cerrar un lote libera de verdad lo aprobado y bloquea lo pendiente,
con el manifiesto de entrega ya filtrable por lote; con la Fase 8
completa (ver más arriba) los siete documentos de la sección 7.1 --seis
informes CSV más el acta de cierre de lote en Markdown-- se generan de
verdad a partir de los datos ya existentes, sin ninguna tabla nueva; con
la Fase 9 completa (ver más arriba) el flujo completo ya corrió de
verdad sobre un documento real del corpus confirmado en el Anexo B, con
resultado APROBADO contra los criterios de las secciones 8.1/8.2; con la
Fase 10 completa (ver más arriba) cualquier proyecto ya puede
respaldarse cifrado (Fernet, clave en `keyring`) y restaurarse, con la
integridad y la clave verificadas antes de descifrar; y
el Módulo 13 ya bloquea de verdad la aprobación/liberación en sus tres casos:
incidencias críticas abiertas, documentos críticos con vigencia
desconocida (2026-07-28), y no liberar sin fuente/hash/aprobación
(2026-07-28).

**Orden recomendado para lo que falta hasta considerar la herramienta
completa** (mismo criterio de dependencias que ya justificó construir
el Módulo 10 antes que la GUI -- decisión explícita del cliente,
2026-07-28): (1) *completo* -- Módulo 13, primera regla (incidencias
críticas); (2) *completo* -- terminar el Módulo 8 (corrección,
verificación de fechas/cifras, navegación sincronizada real); (3)
*completo* -- Módulo 11 (Vigencias y fuentes); (4) *completo* -- Módulo
13, segunda regla (vigencia desconocida); (5) *completo* -- Módulo 12
(Generador de Markdown, hasta LIBERADO, backend sin GUI -- mismo
criterio que el Módulo 9); (6) *completo* -- colas de trabajo y workers
aislados (`workers/cola_de_trabajos.py`, backend sin GUI -- mismo
criterio que los Módulos 9 y 12; el panel de monitoreo de trabajos en
ejecución queda para la Fase 11); (7) *completo* -- Lotes
(`domain.batches`/`application.batches`, `CerrarLote` libera lo
aprobado y bloquea lo pendiente; "firmar acta y exportar" quedó para la
Fase 8); (8) *completo* -- Reportes y
documentación automática (`domain.reports`/`application.reports`,
sección 7.1: seis informes CSV más el acta de cierre de lote en
Markdown, todos recalculados en el momento, backend sin GUI -- mismo
criterio que los Módulos 9 y 12; el acta de cierre de lote que la
Fase 7 dejó pendiente ya se genera de verdad); (9) *completo* -- módulo
de pruebas de aceptación sobre datos reales
(`domain.acceptance`/`application.acceptance`, sección 8.1, distinto de
la suite de pytest de este propio código: corre el flujo real completo
sobre `corpus_aceptacion/documentos/`, hoy con
`plan_estudios_electromecanica.pdf` -- el archivo real confirmado en el
Anexo B del Documento Maestro, 2026-07-28 --, produciendo un informe
humano-legible contra los criterios de las secciones 8.1/8.2 vía
`scripts/ejecutar_pruebas_aceptacion.py`; los dominios OCR/transcripción/
legado quedan `PENDIENTE`, no `FALLA`, hasta que se agreguen más
archivos representativos); (10) *completo* -- seguridad y distribución
-- simplificado a lo estrictamente necesario para uso personal
(confirmado 2026-07-28, Anexo B: no es una herramienta comercial, sin
presupuesto/calendario formal que definir): respaldos cifrados
(`domain.security`/`application.security`, Fernet, clave en el almacén
de credenciales del sistema operativo vía `keyring`), pruebas de
restauración que reportan en vez de lanzar excepciones, borrado seguro
del zip intermedio sin cifrar, y manual de operación propio
(`MANUAL_OPERACION.md`) -- sin empaquetado/instalador ni actualizaciones
automáticas, backend sin GUI vía `scripts/gestionar_respaldos.py` --
mismo criterio que los Módulos 9/12 y las Fases 6/7/8/9; (11)
**completo (2026-07-29)** -- interfaz completa (menú funcional +
asistente por etapas + pantalla principal, sección 4.11), construida en
tres pasadas incrementales (Fases 11, 11.2 y 11.3, ver más arriba) --
mismo criterio con el que se construyó el propio Módulo 8. Usuarios y
roles quedan deliberadamente fuera de esta secuencia: la "colaboración
simultánea centralizada" está fuera de alcance de la primera versión
(sección 4, "no incluye"). Con esto, las once áreas de la hoja de ruta
original quedan completas.

Ver Documento Maestro, sección 7 (hoja de ruta), y ADR-001, sección 15.
# RAG-CONTENT
