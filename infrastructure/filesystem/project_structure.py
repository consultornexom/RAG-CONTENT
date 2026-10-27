"""Adaptador de ProjectFileStore sobre el sistema de archivos local
(ADR-001, seccion 4: infrastructure implementa los puertos de domain).

Crea la estructura fisica exacta del Documento Maestro, seccion 4.5:
14 subcarpetas + proyecto.yaml, siempre dentro de la ruta raiz unica
confirmada (Documento Maestro, seccion 4.1) -- nunca fuera de ella.

14_entrega_rag_studio/ se agrego el 2026-07-31 (comentario real del
consultor: consolidar en una sola carpeta lo que se debe entregar a RAG
STUDIO, ver domain.documents.ports.EntregaRagStudioStore) -- proyectos
creados con una version anterior de la herramienta no la tienen desde
`create_structure()`, pero `LocalEntregaRagStudioStore.preparar()` la
crea de todos modos la primera vez que se usa (mismo criterio que
`LocalReportWriter`/`CsvManifestWriter`, que tampoco dependen de que
`create_structure()` haya corrido con la version mas reciente)."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from domain.projects.entities import Proyecto
from domain.projects.exceptions import ProjectFolderAlreadyExistsError
from domain.projects.ports import ProjectFileStore

SUBCARPETAS: tuple[str, ...] = (
    "01_originales",
    "02_inventario",
    "03_extracciones",
    "04_transcripciones",
    "05_revisiones",
    "06_normalizados",
    "07_markdown",
    "08_incidencias",
    "09_evidencias",
    "10_reportes",
    "11_logs",
    "12_exportaciones",
    "13_respaldos",
    "14_entrega_rag_studio",
)
"""Orden y nombres exactos del Documento Maestro, seccion 4.5."""


class LocalProjectFileStore(ProjectFileStore):
    def __init__(self, proyectos_root: Path):
        self._proyectos_root = proyectos_root

    def create_structure(self, proyecto: Proyecto) -> str:
        carpeta = self._proyectos_root / proyecto.carpeta_normalizada()
        if carpeta.exists():
            raise ProjectFolderAlreadyExistsError(str(carpeta))

        carpeta.mkdir(parents=True, exist_ok=False)
        for nombre in SUBCARPETAS:
            (carpeta / nombre).mkdir()

        manifiesto = {
            "id": proyecto.id,
            "nombre": proyecto.nombre,
            "perfil_id": proyecto.perfil_id,
            "objetivo": proyecto.objetivo,
            "confidencialidad": proyecto.confidencialidad.value,
            "creado": proyecto.created_at.isoformat(),
        }
        (carpeta / "proyecto.yaml").write_text(
            yaml.safe_dump(manifiesto, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        return str(carpeta)

    def delete_structure(self, proyecto: Proyecto) -> None:
        # Auditoria 2026-09-02 (RAG_CONTENT_01): a diferencia de
        # `create_structure()`, aqui NO se ignoran errores -- si
        # `shutil.rmtree` falla (permisos, proyecto.db con un handle
        # abierto...), se deja que la excepcion se propague. Quien
        # llama (EliminarProyecto) solo borra el registro del indice
        # global DESPUES de que esto termine sin errores; invertir el
        # orden dejaria un proyecto invisible en la app con sus archivos
        # todavia en disco, sin ningun aviso (mismo hallazgo real que
        # motivo esta misma correccion en RAG STUDIO, Ronda 4 de
        # Validacion_observaciones_RAG_STUDIO.md).
        carpeta = Path(proyecto.ruta_carpeta) if proyecto.ruta_carpeta else None
        if carpeta is not None and carpeta.exists():
            shutil.rmtree(carpeta)
