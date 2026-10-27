"""Caso de uso: recuperar documentos huerfanos que quedaron atascados en
EN_EXTRACCION o EN_NORMALIZACION (Documento Maestro, seccion 4.1:
"recuperacion"). Se ejecuta una sola vez, automaticamente, al abrir un
proyecto (`app.bootstrap.abrir_proyecto()`) -- mismo principio de "el
operador nunca lo ejecuta a mano" que ya aplica
`RecuperarTrabajosInterrumpidos` para el contexto Trabajos.

Bug real encontrado 2026-07-29 (usuario sin Tesseract instalado, ver
domain.documents.entities.Documento.marcar_extraccion_fallida()/
marcar_normalizacion_fallida()): antes de esta fecha, un fallo del
extractor o del motor de normalizacion dejaba el documento guardado en
EN_EXTRACCION/EN_NORMALIZACION sin ningun try/except que lo revirtiera.
Ese defecto ya esta corregido para fallos NUEVOS (ver
application.documents.commands.extraer_documento.ExtraerDocumento y
normalizar_documento.NormalizarDocumento), pero no repara, por si solo,
los documentos que un usuario ya tenia atascados en su proyecto ANTES de
actualizar la aplicacion -- de ahi este caso de uso, que corre al abrir
el proyecto y los revierte al estado retomable (CLASIFICADO/REVISADO)
igual que si el fallo hubiera ocurrido con la version corregida."""
from __future__ import annotations

from domain.documents.entities import Documento, EstadoDocumento
from domain.documents.ports import DocumentRepository
from domain.projects.ports import AuditLogger


class RecuperarDocumentosInterrumpidos:
    def __init__(self, repository: DocumentRepository, audit: AuditLogger):
        self._repository = repository
        self._audit = audit

    def execute(self) -> list[Documento]:
        huerfanos = self._repository.list_by_estado(
            EstadoDocumento.EN_EXTRACCION
        ) + self._repository.list_by_estado(EstadoDocumento.EN_NORMALIZACION)
        recuperados = []
        for documento in huerfanos:
            documento = (
                documento.marcar_extraccion_fallida()
                if documento.estado == EstadoDocumento.EN_EXTRACCION
                else documento.marcar_normalizacion_fallida()
            )
            self._repository.save(documento)
            self._audit.record(
                proyecto_id=documento.proyecto_id,
                accion="recuperar_documento_interrumpido",
                valor_anterior=None,
                valor_nuevo=documento.estado.value,
                motivo="Documento huerfano tras un fallo sin manejar de una version anterior o un cierre "
                "no controlado de la aplicacion (Documento Maestro, seccion 4.1: 'recuperacion').",
            )
            recuperados.append(documento)
        return recuperados
