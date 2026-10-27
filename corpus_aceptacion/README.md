# Corpus de aceptación (Fase 9)

Documentos reales y representativos usados para validar la herramienta
misma contra la sección 8.1 ("Pruebas mínimas por dominio") y la
sección 8.2 ("Umbrales recomendados de liberación") del Documento
Maestro — distinto de la suite de `pytest` del propio código (que
verifica que el código funciona; esto verifica que la herramienta
completa se comporta bien sobre documentos reales, no sintéticos).

Confirmado en el Anexo B del Documento Maestro (2026-07-28): el
consultor ya cuenta con archivos de prueba representativos.

## Cómo se usa

Cualquier archivo dentro de `documentos/` (en cualquier subcarpeta, se
recorre recursivamente) se procesa a través del flujo real completo
(registro, clasificación, extracción, revisión, normalización, fuente,
vigencia, aprobación, generación de Markdown, validación, liberación,
lote y acta de cierre) al ejecutar:

```bash
python scripts/ejecutar_pruebas_aceptacion.py
```

El informe resultante se escribe dentro de `informes/` (Markdown,
nombrado con la fecha de la corrida) y NO se sobrescribe entre
corridas — cada ejecución queda archivada.

No hace falta clasificar los archivos por carpeta según su ruta de
procesamiento esperada: el propio Módulo 4 (clasificación) decide, para
cada archivo, si corresponde extracción directa, OCR o transcripción,
igual que con cualquier documento real que un operador registre desde
la interfaz.

## Cobertura actual del corpus

- `plan_estudios_electromecanica.pdf` — PDF con capa de texto real (no
  escaneado): ejercita el dominio "Extracción" por la ruta de
  extracción directa, además de "Normalización", "Markdown",
  "Trazabilidad" y "Liberación".

**Dominios de la sección 8.1 todavía sin corpus real** (el informe los
marca como pendientes, nunca como aprobados ni como fallidos, hasta que
se agregue al menos un archivo representativo):

- **OCR** — falta un PDF escaneado o una imagen (PNG/JPG) sin capa de
  texto.
- Un archivo de **audio o video** para ejercitar transcripción
  (Módulo 7).
- Un archivo **DOC/XLS** legado para ejercitar la conversión previa vía
  LibreOffice (Módulo 4).

Agregar estos archivos a `documentos/` es suficiente — no hace falta
tocar ningún código: la próxima corrida del script los detecta solos
por su formato.
