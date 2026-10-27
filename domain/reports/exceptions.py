"""Excepciones del contexto Reportes (Fase 8)."""
from __future__ import annotations


class ReportDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class LoteNoCerradoParaActaError(ReportDomainError):
    """Se intento generar el acta de cierre de un lote que todavia esta
    ABIERTO -- el acta describe COMO se cerro el lote (liberados,
    bloqueados, exclusiones; Documento Maestro, seccion 7.1), asi que no
    tiene contenido real hasta que
    `application.batches.commands.cerrar_lote.CerrarLote` haya
    terminado. A diferencia de los otros seis informes (que reflejan el
    estado actual del proyecto completo, sin precondicion), el acta es
    el unico documento de este contexto atado al estado de otra entidad
    (`domain.batches.entities.Lote`)."""

    def __init__(self, lote_id: str):
        super().__init__(
            f"No se puede generar el acta de cierre del lote '{lote_id}': todavia esta "
            "ABIERTO. Cierrelo primero (CerrarLote) antes de generar su acta."
        )
        self.lote_id = lote_id
