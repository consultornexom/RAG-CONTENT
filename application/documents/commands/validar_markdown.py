"""Caso de uso del Modulo 12: validacion tecnica del Markdown final ya
generado -- MARKDOWN_GENERADO -> VALIDADO en un solo paso atomico.

Dos verificaciones:
1. Bloqueante: el contenido no puede estar vacio (una normalizacion que
   produjo un archivo vacio es una senal real de un insumo vacio o un
   bug -- vale la pena detener el flujo aqui en vez de liberar un
   documento sin contenido util).
2. No bloqueante: si el Markdown no tiene ningun encabezado ni tabla
   real (domain.documents.estructura_markdown.tiene_estructura_markdown()),
   se registra como advertencia -- RAG STUDIO fragmentara el documento
   como un solo bloque (Documento Maestro, seccion 4.6.1), lo cual puede
   ser aceptable (un memo corto) o no, pero la decision es del operador,
   nunca de este caso de uso."""
from __future__ import annotations

from pathlib import Path

from domain.documents.entities import Documento
from domain.documents.estructura_markdown import tiene_estructura_markdown
from domain.documents.exceptions import DocumentNotFoundError, MarkdownVacioError
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger


class ValidarMarkdown:
    def __init__(self, repository: DocumentRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self, documento_id: str) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)
        if documento.ruta_markdown is None:
            raise ValueError(
                f"El documento '{documento_id}' esta en estado '{documento.estado.value}' pero no tiene "
                "ruta_markdown -- no se puede validar sin haber generado antes el Markdown final."
            )

        contenido = Path(documento.ruta_markdown).read_text(encoding="utf-8")
        if not contenido.strip():
            raise MarkdownVacioError(documento_id)

        advertencias: list[str] = []
        if not tiene_estructura_markdown(contenido):
            advertencias.append(
                "El Markdown final no tiene ningun encabezado ni tabla real -- RAG STUDIO lo "
                "fragmentara como un solo bloque al registrarlo como fuente (Documento Maestro, "
                "seccion 4.6.1)."
            )

        documento = documento.validar_markdown(advertencias)
        self._repository.save(documento)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="validar_markdown",
            valor_anterior=None,
            valor_nuevo=f"{len(advertencias)} advertencia(s)",
            motivo="Validacion tecnica del Markdown final antes de liberar (Documento Maestro, Modulo 12).",
        )
        return documento
