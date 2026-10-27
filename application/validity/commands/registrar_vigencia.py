"""Caso de uso: registrar (o actualizar) la Vigencia de un documento
(Modulo 11, Documento Maestro seccion 4.6, fila 11).

Mismo patron de validacion cruzada que RegistrarFuente: valida que
`documento_id` exista, y si se indica `sustituye_a`, valida tambien que
ese otro documento exista en el mismo inventario -- ambas resueltas
aqui en application, domain.validity no importa domain.documents.

Upsert, no alta estricta -- ver el docstring de RegistrarFuente para el
razonamiento completo (aqui aplica igual)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from domain.documents.exceptions import DocumentNotFoundError
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger
from domain.validity.entities import Vigencia
from domain.validity.ports import VigenciaRepository


class RegistrarVigencia:
    def __init__(
        self,
        repository: VigenciaRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._repository = repository
        self._document_repository = document_repository
        self._audit = audit

    def execute(
        self,
        documento_id: str,
        fecha_emision: Optional[date],
        vigente_desde: Optional[date],
        vigente_hasta: Optional[date],
        sin_vencimiento: bool,
        autoridad: str,
        sustituye_a: Optional[str] = None,
    ) -> Vigencia:
        documento = self._document_repository.get(documento_id)
        if documento is None:
            raise DocumentNotFoundError(documento_id)
        if sustituye_a and self._document_repository.get(sustituye_a) is None:
            raise DocumentNotFoundError(sustituye_a)

        existente = self._repository.get_by_document(documento_id)
        if existente is not None:
            vigencia = existente.actualizar(
                fecha_emision, vigente_desde, vigente_hasta, sin_vencimiento, autoridad, sustituye_a
            )
        else:
            vigencia = Vigencia(
                documento_id=documento_id,
                fecha_emision=fecha_emision,
                vigente_desde=vigente_desde,
                vigente_hasta=vigente_hasta,
                sin_vencimiento=sin_vencimiento,
                autoridad=autoridad,
                sustituye_a=sustituye_a,
            )
        self._repository.save(vigencia)
        self._audit.record(
            proyecto_id=documento.proyecto_id,
            accion="registrar_vigencia",
            valor_anterior=None,
            valor_nuevo="completa" if vigencia.esta_completa() else "incompleta (vigencia desconocida)",
            motivo="Alta o actualizacion de la vigencia del documento (Documento Maestro, Modulo 11).",
        )
        return vigencia
