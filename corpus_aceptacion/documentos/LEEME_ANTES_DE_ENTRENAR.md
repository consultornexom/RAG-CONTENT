# Antes de entrenar con estos archivos

Esta carpeta **no es un corpus de entrenamiento**. 10 de sus 26 documentos estan reservados, y usarlos rompe la medicion sin que se note: el numero final sigue pareciendo limpio.

Generado por `tools/corpus_partition.py` del proyecto MODEL ADAPTATION
STUDIO. **No editar a mano**: se regenera.

## PROHIBIDO — sustentan `EVALSET-2026-001`

Sus respuestas de oro salen de aqui. Entrenar con ellos es ensenarle al
modelo las respuestas del examen. La prohibicion de NEXOM **no admite
waiver**.

| Archivo | Programa |
|---|---|
| `admemp.pdf` | Administración de Empresas |
| `arq.pdf` | Arquitectura |
| `der.pdf` | Derecho |
| `ingcom.pdf` | Ingeniería en Computación |
| `psi.pdf` | Psicología |

## CONGELADOS — holdout de aceptacion

Se miran **una vez**, al final, sobre el candidato ya elegido. Usarlos
antes los gasta y no hay forma de recuperarlos.

| Archivo |
|---|
| `dismod.pdf` |
| `ingele.pdf` |
| `ingind.pdf` |
| `negint.pdf` |
| `plan_estudios_electromecanica.pdf` |

## Disponibles para entrenar: 16

Los demas. El reparto completo, con hashes, esta en
`corpus/PARTICION_CORPUS.json` del proyecto.

El control no depende de este archivo: la comprobacion se hace por
SHA-256 al registrar el dataset, asi que renombrar o copiar un PDF
reservado no la burla. Este aviso existe para que nadie llegue hasta
ahi por descuido.

**El texto extraido hereda la reserva.** El Markdown que produjo el
OCR tiene otro hash que su PDF, pero no otro permiso: la particion
registra el enlace para que la prohibicion lo alcance.
