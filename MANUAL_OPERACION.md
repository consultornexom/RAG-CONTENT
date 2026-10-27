# Manual de operación — RAG Content Studio Desktop

Manual propio de la herramienta (Fase 10, "Seguridad y distribución";
Documento Maestro, sección 9: "instrucciones de operación, respaldo,
recuperación y mantenimiento"; ADR-001, sección 14.3). Cubre las
operaciones que un consultor que use esta herramienta en su propio
equipo necesita hacer a mano, ya que la interfaz gráfica (Fase 11)
todavía no tiene pantallas para esto.

No es un manual de instalación de librerías Python (ver "Instalación"
en `README.md`) ni un manual de uso de la interfaz gráfica: es,
específicamente, el procedimiento de respaldo/restauración y la gestión
de la clave que los protege, más la reparación de lotes de entrega
generados en Windows con versiones anteriores al 2026-09-30 (sección 8).

## 1. Dónde vive la carpeta raíz de datos

Toda la información de la herramienta (perfiles, proyectos, logs, la
base de datos global) vive dentro de una única carpeta raíz (Documento
Maestro, sección 4.1). Bug real encontrado 2026-07-30: hasta esa fecha,
esa carpeta era una ruta de Linux hardcodeada en el código
(`/media/disco/Data/RAG CONTENT STUDIO`, el disco del consultor) —
funcionaba mientras la única máquina real era esa, pero en Windows esa
misma cadena se interpretaba de forma inesperada (relativa a la unidad
de trabajo actual), dejando los proyectos en un lugar no obvio para el
usuario. Ya corregido: `app.configuration.cargar_rutas()` resuelve la
carpeta raíz en este orden:

1. Un argumento explícito (solo lo usan las pruebas automatizadas).
2. La variable de entorno `RAG_CONTENT_STUDIO_ROOT`, si está definida
   — fíjela antes de iniciar la aplicación para usar una carpeta
   distinta a la que toca por defecto (por ejemplo, para conservar una
   instalación existente, o para apuntar a un disco de red compartido).
3. Si ninguna de las dos anteriores aplica: una carpeta llamada
   `RAG Content Studio Desktop` dentro del home del usuario que corre
   la aplicación — el mismo nombre en Windows, macOS y Linux, calculado
   en tiempo de ejecución (`Path.home()`), nunca una ruta fija.

Para fijar la variable de entorno de forma permanente:

- **Windows** (PowerShell, una sola vez):
  `[Environment]::SetEnvironmentVariable("RAG_CONTENT_STUDIO_ROOT", "D:\Datos\RAG Content Studio Desktop", "User")`
- **macOS/Linux** (agregar al perfil de la shell, por ejemplo
  `~/.bashrc` o `~/.zshrc`):
  `export RAG_CONTENT_STUDIO_ROOT="/ruta/que/quiera/usar"`

## 2. Respaldar un proyecto

Un respaldo es una copia cifrada de la carpeta completa de un proyecto
(originales, extracciones, revisiones, normalizados, Markdown,
incidencias, evidencias, reportes, logs, exportaciones, la entrega
consolidada para RAG Studio — las 14 subcarpetas del Documento Maestro,
sección 4.5, salvo `13_respaldos/` en sí misma). Corregido 2026-07-31
(auditoría general): este manual todavía contaba 13 subcarpetas, un
número que quedó desactualizado el 2026-07-31 al agregarse
`14_entrega_rag_studio/` (carpeta consolidada con una copia del
manifiesto y de cada Markdown liberado, pensada para entregar de una
vez a RAG Studio). Corregido 2026-10-03 (NEXOM, entregas separadas por
lote con versión): la entrega de **todo el proyecto** (sin indicar un
lote) sigue regenerándose en la raíz de `14_entrega_rag_studio/` en
cada corrida, igual que antes; pero la entrega **de un lote**
(`"Ir a Reportes"`/"Cerrar lote" del Asistente, o "Exportar entrega de
este lote..." del panel "Lotes") ya NO se borra entre corridas: cada
vez que se (re)exporta un lote se crea una subcarpeta nueva
`14_entrega_rag_studio/<id_lote>_<nombre_del_lote>/v1/`,
`.../v2/`, etc., y las versiones anteriores de ese mismo lote (y las
carpetas de cualquier otro lote) se conservan intactas. Un respaldo
antiguo puede entonces tener menos versiones de las que existen hoy en
el proyecto; esto no es un problema, es el mismo comportamiento
esperado de cualquier carpeta derivada (como `07_markdown/`) dentro de
un respaldo. Se guarda dentro de la propia carpeta del proyecto, en
`13_respaldos/`, como un archivo `respaldo_<fecha>.zip.enc`.

```bash
python scripts/gestionar_respaldos.py listar
python scripts/gestionar_respaldos.py crear PROY-0001
```

El primer comando muestra el id, nombre y carpeta de cada proyecto
existente. El segundo crea un respaldo nuevo del proyecto indicado e
imprime la ruta del archivo, su hash SHA-256 (para verificar
integridad más adelante) y su tamaño.

La **primera vez** que se respalda un proyecto, la herramienta genera
una clave de cifrado nueva y la guarda en el almacén de credenciales
del sistema operativo (ver sección 4). Los respaldos **siguientes**
del mismo proyecto reutilizan esa misma clave — no hay una clave
distinta por archivo.

Se recomienda respaldar antes de cualquier operación grande sobre un
proyecto (cierre de lote, generación de Markdown de todo el proyecto,
limpieza manual de archivos) y periódicamente durante el uso normal.
Esta versión no automatiza esa periodicidad (ver sección 6) — es una
tarea manual del consultor.

## 3. Restaurar un respaldo

```bash
python scripts/gestionar_respaldos.py restaurar PROY-0001 \
    "<carpeta raiz>/proyectos/PROY-0001_mi_proyecto/13_respaldos/respaldo_20260729T060000.zip.enc" \
    /ruta/donde/restaurar
```

(`<carpeta raiz>` es la que resuelve `app.configuration.cargar_rutas()`
-- ver sección 1: por defecto, una carpeta dentro del home del usuario,
salvo que RAG_CONTENT_STUDIO_ROOT indique otra.)

El tercer argumento es la carpeta de destino — se crea si no existe.
**Nunca restaura sobre la carpeta original del proyecto**: es
responsabilidad del consultor mover el contenido restaurado a donde
corresponda después de revisarlo, para no arriesgar sobrescribir datos
vigentes con una restauración equivocada.

Una restauración puede terminar de dos formas:

- **Exitosa**: se imprime la ruta de destino. El contenido restaurado
  es idéntico al que tenía el proyecto en el momento de crear ese
  respaldo.
- **No exitosa**: se imprime el motivo (clave incorrecta, archivo
  corrupto o alterado después de crearse, o una ruta interna del
  respaldo que intentaría escribir fuera de la carpeta de destino). Una
  restauración no exitosa **no es un error de la herramienta** — es
  precisamente el resultado que una "prueba de restauración" (Documento
  Maestro, sección 9) existe para detectar: un respaldo que nunca se
  probó restaurar no está realmente verificado, solo se asume íntegro
  por existir. Ante un resultado no exitoso, el respaldo en cuestión
  debe considerarse no confiable y no debe ser el único respaldo
  disponible de ese proyecto.

Se recomienda probar la restauración de un respaldo periódicamente
(por ejemplo, cada pocos respaldos nuevos), no solo cuando de verdad se
necesite recuperar algo — es la única forma de confirmar que un
respaldo servirá el día que de verdad haga falta.

## 4. La clave de cifrado

La clave de cifrado de los respaldos de cada proyecto se guarda en el
almacén de credenciales del sistema operativo (Secret Service/GNOME
Keyring o KWallet en Linux, Credential Manager en Windows, Keychain en
macOS) a través de la librería `keyring` — nunca en un archivo propio
de la aplicación, nunca en texto plano, nunca en ningún log. Es la
misma librería y el mismo criterio que usa RAG STUDIO para sus propias
credenciales (ADR-001, sección 14.1).

**No existe ningún mecanismo de recuperación de clave perdida en esta
versión.** Si el almacén de credenciales del sistema operativo se
pierde, se reinstala, o se limpia manualmente (por ejemplo, al
reinstalar el sistema operativo sin migrar el llavero), **todos los
respaldos existentes de todos los proyectos, pasados y futuros, quedan
irrecuperables por igual** — cifrados con una clave que ya no existe
en ningún lado.

Implicaciones prácticas:

- Antes de reinstalar el sistema operativo o cambiar de equipo, migrar
  el almacén de credenciales (por ejemplo, exportar el llavero de GNOME
  Keyring) es tan importante como copiar los archivos `.zip.enc`
  mismos.
- Un respaldo `.zip.enc` copiado a un disco externo o a otra máquina
  **no sirve por sí solo** sin la clave correspondiente en el almacén
  de credenciales de esa máquina.
- No hay forma de "ver" la clave desde esta herramienta (ni desde
  `scripts/gestionar_respaldos.py` ni desde ningún caso de uso) — es
  una decisión deliberada, no una limitación a resolver: mostrarla
  rompería el principio de "nunca en texto plano, nunca en logs"
  (ADR-001, sección 14.3).

## 5. Niveles de acceso y confidencialidad

Cada proyecto tiene un nivel de confidencialidad
(público/interno/confidencial/restringido) asignado al crearlo — mismo
catálogo que `access_level` en RAG STUDIO (ADR-001, sección 14.3). Este
campo ya existe desde la Fase 1 (`domain.projects.entities.
NivelConfidencialidad`); la Fase 10 no agrega nada nuevo aquí, solo lo
documenta como parte de la política de seguridad completa de la
herramienta.

## 6. Qué NO hace esta versión

Por alcance confirmado (Anexo B, 2026-07-28 — herramienta de uso
personal, no comercial):

- No hay empaquetado ni instalador (`.deb`, `.exe`, `.dmg`) — se corre
  desde el entorno de desarrollo Python, como el resto de esta
  herramienta.
- No hay actualizaciones automáticas.
- No hay una política de retención automática de respaldos (borrado de
  respaldos antiguos, rotación) — los respaldos se acumulan en
  `13_respaldos/` hasta que el consultor los borre a mano. Queda
  pendiente de definir junto con el "primer perfil de proyecto" (Anexo
  B, sin resolver todavía).
- Corregido 2026-07-31 (auditoría general, afirmación desactualizada
  detectada en este mismo manual): **sí existe** una pantalla en la
  interfaz gráfica para crear/restaurar respaldos, en la pantalla
  "Configuración" del Modo avanzado (`ui.panels.configuracion_panel.
  ConfiguracionPanel`), agregada junto con el resto de la Fase 11
  (Interfaz completa). `scripts/gestionar_respaldos.py` (secciones 2 y
  3 de este manual) sigue existiendo y funcionando igual, como
  alternativa de línea de comandos -- ninguna de las dos formas
  reemplaza a la otra, hacen lo mismo por dos caminos distintos.

## 7. Borrado seguro de temporales

Al crear o restaurar un respaldo, la herramienta usa un archivo
temporal intermedio (el zip sin cifrar) que contiene el contenido
completo del proyecto en texto claro. Ese archivo se sobrescribe con
bytes aleatorios antes de eliminarse, en vez de borrarse directamente —
esto ocurre automáticamente, sin ninguna acción del consultor, tanto si
la operación termina bien como si falla a la mitad.

## 8. Reparar un lote que RAG Studio rechaza por hash (lotes generados en Windows antes del 2026-09-30)

**Síntoma.** Al importar la carpeta `14_entrega_rag_studio/` en RAG Studio
aparece "Importadas: 0" y cada archivo dice "el archivo fue localizado, pero
su contenido no coincide con el hash declarado en el manifiesto".

**Causa.** Las versiones anteriores al 2026-09-30 guardaban el Markdown en
Windows con fines de línea `\r\n`, pero declaraban en el manifiesto el hash
del texto con `\n`. El contenido es el mismo; solo cambian los fines de
línea. Desde esta versión los archivos se escriben igual en cualquier
sistema operativo y "Preparar entrega para RAG Studio" verifica cada hash
antes de dejar lista la carpeta: si algo no coincide, no deja la entrega y
muestra qué archivos fallan.

**Reparación.** El script solo usa Python estándar; puede ejecutarse en el
equipo de RAG Studio aunque no tenga RAG Content instalado. Sin `--aplicar`
solo informa.

```bash
# a) La carpeta de entrega que ya se copió al otro equipo (lo más rápido):
python scripts/reparar_fin_de_linea_markdown.py "/ruta/14_entrega_rag_studio"
python scripts/reparar_fin_de_linea_markdown.py "/ruta/14_entrega_rag_studio" --aplicar

# b) El proyecto completo en el equipo Windows (con RAG Content CERRADO):
python scripts/reparar_fin_de_linea_markdown.py "D:\...\proyectos\PROY-0000_nombre" --aplicar
#    y después, en la aplicación: "Preparar entrega para RAG Studio".
```

**Entregas por lote (2026-10-03):** el script busca `manifiesto.csv`
directamente DENTRO de la carpeta que se le indique -- con una entrega
de todo el proyecto eso es `14_entrega_rag_studio/` tal cual, pero con
una entrega por lote el manifiesto vive un nivel más adentro, en la
carpeta de la versión concreta que se quiere reparar. Apunte el caso a)
a esa subcarpeta, no a `14_entrega_rag_studio/` directamente:

```bash
python scripts/reparar_fin_de_linea_markdown.py \
    "/ruta/14_entrega_rag_studio/<id_lote>_<nombre_del_lote>/v1" --aplicar
```

La ruta exacta de cada versión se muestra en la aplicación al cerrar el
lote o al usar "Exportar entrega de este lote..." (panel "Lotes").

Reglas del script:

- Solo reescribe un archivo si su única diferencia con el hash declarado
  son los `\r\n`. Nunca cambia el hash ni el manifiesto.
- Un archivo con contenido realmente distinto aparece como `NO REPARABLE`
  y no se toca; también las filas ambiguas y las rutas que salgan de la
  carpeta.
- Antes de reescribir copia los originales a una carpeta
  `..._respaldo_crlf_<fecha>`: junto a la carpeta de entrega en el caso a)
  y dentro del proyecto en el caso b).
- Código de salida 0: todos los archivos coinciden al terminar. 1: queda
  alguno sin coincidir. 2: la carpeta no tiene `manifiesto.csv` ni
  `proyecto.db`.

Se recomienda el caso b) aunque ya se haya hecho el a): si no, la próxima
"Preparar entrega" de ese proyecto volverá a ser rechazada por la
verificación previa.
