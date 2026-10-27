"""Caso de uso: registrar un documento en el inventario (Modulo 3,
Documento Maestro Anexo B: "inventario documental con hash SHA-256").
Mirror funcional de RegisterSource en RAG STUDIO
(application/documents/commands/register_source.py), adaptado a la
regla de "originales inmutables" mas estricta de este proyecto (ver
domain.documents.entities.Documento.ruta_copia_original).
"""
from __future__ import annotations

from pathlib import Path

from domain.documents.entities import Criticidad, Documento, EstadoDocumento, FormatoDocumento, Prioridad
from domain.documents.exceptions import DuplicateDocumentHashError, UnsupportedFormatError
from domain.documents.ports import DocumentRepository, OriginalFileStore
from domain.projects.ports import AuditLogger

_EXTENSION_A_FORMATO: dict[str, FormatoDocumento] = {
    "pdf": FormatoDocumento.PDF,
    "docx": FormatoDocumento.DOCX,
    "doc": FormatoDocumento.DOC,
    "xlsx": FormatoDocumento.XLSX,
    "xls": FormatoDocumento.XLS,
    "csv": FormatoDocumento.CSV,
    "txt": FormatoDocumento.TXT,
    "md": FormatoDocumento.MARKDOWN,
    "markdown": FormatoDocumento.MARKDOWN,
    "json": FormatoDocumento.JSON,
    "png": FormatoDocumento.PNG,
    "jpg": FormatoDocumento.JPG,
    "jpeg": FormatoDocumento.JPG,
    "mp3": FormatoDocumento.MP3,
    "wav": FormatoDocumento.WAV,
    "m4a": FormatoDocumento.M4A,
    "mp4": FormatoDocumento.MP4,
    "mov": FormatoDocumento.MOV,
}


def _inferir_formato(ruta_origen: str) -> FormatoDocumento:
    extension = Path(ruta_origen).suffix.lower().lstrip(".")
    formato = _EXTENSION_A_FORMATO.get(extension)
    if formato is None:
        raise UnsupportedFormatError(ruta_origen, extension)
    return formato


class RegistrarDocumento:
    def __init__(
        self,
        repository: DocumentRepository,
        files: OriginalFileStore,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._files = files
        self._audit = audit

    def execute(
        self,
        proyecto_id: str,
        ruta_origen: str,
        metadatos: dict[str, str] | None = None,
        prioridad: Prioridad = Prioridad.NORMAL,
        criticidad: Criticidad = Criticidad.NO_CRITICO,
    ) -> Documento:
        formato = _inferir_formato(ruta_origen)

        ruta_copia, hash_sha256, tamano_bytes = self._files.copiar_original(ruta_origen)

        existente = self._repository.get_by_hash(hash_sha256)
        if existente is not None:
            # Bug real encontrado en auditoria 2026-07-31: si el mismo
            # contenido se registra con un NOMBRE de archivo distinto al ya
            # inventariado, `copiar_original` (arriba) ya completo una copia
            # fisica nueva en 01_originales/ -- el nombre de destino incluye
            # el hash Y el nombre original, asi que un nombre distinto no
            # activa el atajo de "ya existe" de `LocalOriginalFileStore` y se
            # duplica el archivo en disco antes de llegar aqui a detectar el
            # duplicado. Si la ruta que acabamos de copiar es distinta de la
            # ya registrada, es una copia huerfana (ningun Documento la va a
            # referenciar nunca) -- se limpia en el momento en vez de dejarla
            # ocupando espacio indefinidamente. Limpieza best-effort: un
            # fallo aqui no debe impedir que se reporte el duplicado real.
            if ruta_copia != existente.ruta_copia_original:
                try:
                    Path(ruta_copia).unlink(missing_ok=True)
                except OSError:
                    pass
            raise DuplicateDocumentHashError(hash_sha256, existente.id)

        documento = Documento(
            proyecto_id=proyecto_id,
            nombre_original=Path(ruta_origen).name,
            formato=formato,
            ruta_origen=ruta_origen,
            ruta_copia_original=ruta_copia,
            hash_sha256=hash_sha256,
            tamano_bytes=tamano_bytes,
            prioridad=prioridad,
            criticidad=criticidad,
            metadatos=metadatos or {},
        )
        documento = documento.avanzar_a(EstadoDocumento.INVENTARIADO)

        self._repository.save(documento)
        self._audit.record(
            proyecto_id=proyecto_id,
            accion="registrar_documento",
            valor_anterior=None,
            valor_nuevo=documento.nombre_original,
            motivo="Alta en el inventario documental (Documento Maestro, Modulo 3).",
        )
        return documento
