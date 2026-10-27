"""Excepciones del contexto Incidencias (Modulo 10)."""
from __future__ import annotations


class IncidentDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class InvalidIncidentStateTransitionError(IncidentDomainError):
    """El ciclo de vida de una incidencia (Documento Maestro, seccion
    4.11.1: "registrar, asignar, resolver o bloquear incidencias") no
    admite saltos ni retrocesos -- mismo principio que
    domain.documents.exceptions.InvalidDocumentStateTransitionError,
    aplicado aqui al ciclo mas simple de una incidencia."""

    def __init__(self, origen: str, destino: str):
        super().__init__(
            f"No se permite pasar la incidencia de '{origen}' a '{destino}' -- el ciclo de "
            "vida (Documento Maestro, seccion 4.11.1) no admite saltos ni retrocesos."
        )
        self.origen = origen
        self.destino = destino


class IncidentNotFoundError(IncidentDomainError):
    def __init__(self, incidencia_id: str):
        super().__init__(f"No se encontro la incidencia '{incidencia_id}' en el proyecto.")
        self.incidencia_id = incidencia_id
