"""Fachada del contexto Vigencias y fuentes (ADR-001, seccion 4: ui
solo depende de application)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger
from domain.validity.entities import Fuente, Vigencia
from domain.validity.ports import FuenteRepository, VigenciaRepository

from .commands.registrar_fuente import RegistrarFuente
from .commands.registrar_vigencia import RegistrarVigencia


class ValidityService:
    def __init__(
        self,
        fuente_repository: FuenteRepository,
        vigencia_repository: VigenciaRepository,
        document_repository: DocumentRepository,
        audit: AuditLogger,
    ):
        self._fuente_repository = fuente_repository
        self._vigencia_repository = vigencia_repository
        self._registrar_fuente = RegistrarFuente(fuente_repository, document_repository, audit)
        self._registrar_vigencia = RegistrarVigencia(vigencia_repository, document_repository, audit)

    def registrar_fuente(
        self, documento_id: str, sistema_origen: str, autoridad: str, evidencia_consulta: str
    ) -> Fuente:
        return self._registrar_fuente.execute(documento_id, sistema_origen, autoridad, evidencia_consulta)

    def registrar_vigencia(
        self,
        documento_id: str,
        fecha_emision: Optional[date],
        vigente_desde: Optional[date],
        vigente_hasta: Optional[date],
        sin_vencimiento: bool,
        autoridad: str,
        sustituye_a: Optional[str] = None,
    ) -> Vigencia:
        return self._registrar_vigencia.execute(
            documento_id, fecha_emision, vigente_desde, vigente_hasta, sin_vencimiento, autoridad, sustituye_a
        )

    def obtener_fuente(self, documento_id: str) -> Optional[Fuente]:
        return self._fuente_repository.get_by_document(documento_id)

    def obtener_vigencia(self, documento_id: str) -> Optional[Vigencia]:
        return self._vigencia_repository.get_by_document(documento_id)
