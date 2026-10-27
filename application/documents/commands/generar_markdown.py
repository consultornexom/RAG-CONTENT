"""Caso de uso del Modulo 12 (Generador de Markdown): entregar, dentro
de 07_markdown/ del proyecto, el documento normalizado completo como
archivo Markdown final -- Documento Maestro, seccion 4.6.1 ("el Modulo
12 debe entregar el documento normalizado completo, nunca fragmentos
sueltos") y seccion 4.7 ("no generar Markdown desde EXTRAIDO": solo es
alcanzable desde APROBADO_PARA_MARKDOWN, que a su vez exige haber
pasado por NORMALIZADO).

APROBADO_PARA_MARKDOWN -> MARKDOWN_GENERADO en un solo paso atomico --
mismo principio que ExtraerDocumento/NormalizarDocumento. Copia el
Markdown vigente en ESE momento (`Documento.ruta_markdown_vigente()`,
que en este punto del flujo es siempre el normalizado) hacia
07_markdown/, en vez de referenciar 06_normalizados/ directamente --
asi el archivo entregado queda fijo aunque el de trabajo interno
cambiara en el futuro (no puede hoy, pero el archivo de entrega no debe
depender de esa garantia)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.exceptions import DocumentNotFoundError, InvalidDocumentStateTransitionError
from domain.documents.ports import DocumentRepository, ExtractionOutputStore
from domain.projects.ports import AuditLogger


class GenerarMarkdown:
    def __init__(self, repository: DocumentRepository, output_store: ExtractionOutputStore, audit: AuditLogger):
        self._repository = repository
        self._output_store = output_store
        self._audit = audit

    def execute(self, documento_id: str) -> Documento:
        documento = self._repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)

        # Se valida el estado ANTES de leer/escribir nada -- a diferencia
        # de ExtraerDocumento/NormalizarDocumento, aqui no existe un
        # estado intermedio ("EN_...") al que avanzar primero, asi que
        # se comprueba explicitamente en vez de dejar que
        # `Documento.generar_markdown()` lo descubra despues de ya haber
        # escrito un archivo en 07_markdown/.
        if documento.estado != EstadoDocumento.APROBADO_PARA_MARKDOWN:
            raise InvalidDocumentStateTransitionError(documento.estado.value, EstadoDocumento.MARKDOWN_GENERADO.value)

        ruta_vigente = documento.ruta_markdown_vigente()
        if ruta_vigente is None:
            # Solo alcanzable por manipulacion directa del repositorio --
            # ver el mismo razonamiento en NormalizarDocumento.execute().
            raise ValueError(
                f"El documento '{documento_id}' esta en estado '{documento.estado.value}' pero no tiene "
                "Markdown vigente -- no se puede generar el archivo de entrega."
            )

        contenido = Path(ruta_vigente).read_text(encoding="utf-8")
        ruta_markdown = self._output_store.guardar(documento.id, contenido)
        # El hash se calcula sobre los BYTES del archivo que realmente se
        # escribio y se entregara, no sobre el texto en memoria: es lo que
        # exige el contrato de intercambio (seccion 4, `hash_contenido` =
        # SHA-256 del .md entregado) y lo que RAG STUDIO verifica. Asi
        # ninguna traduccion de fin de linea, codificacion u otra
        # transformacion del adaptador puede volver a separar el hash
        # declarado del archivo entregado (incidencia 2026-09-30, CRLF en
        # Windows).
        hash_markdown = hashlib.sha256(Path(ruta_markdown).read_bytes()).hexdigest()

        documento = documento.generar_markdown(ruta_markdown, hash_markdown)
        self._repository.save(documento)

        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="generar_markdown",
            valor_anterior=None,
            valor_nuevo=ruta_markdown,
            motivo="Generacion del Markdown final de entrega hacia RAG STUDIO (Documento Maestro, Modulo 12).",
        )
        return documento
