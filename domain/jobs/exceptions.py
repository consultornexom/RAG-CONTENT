"""Excepciones del contexto Trabajos."""
from __future__ import annotations


class JobDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class InvalidJobStateTransitionError(JobDomainError):
    def __init__(self, origen: str, destino: str):
        super().__init__(
            f"No se permite pasar el trabajo de '{origen}' a '{destino}' -- ver "
            "ADR-001, seccion 10, y domain.jobs.entities._TRANSICIONES."
        )
        self.origen = origen
        self.destino = destino


class JobNotFoundError(JobDomainError):
    def __init__(self, trabajo_id: str):
        super().__init__(f"No se encontro el trabajo '{trabajo_id}' en la cola del proyecto.")
        self.trabajo_id = trabajo_id


class ReintentosAgotadosError(JobDomainError):
    """El trabajo ya fallo `max_intentos` veces -- Documento Maestro,
    seccion 4.1: "reintentos" no significa reintentos ilimitados. Se
    necesita intervencion humana (revisar el `mensaje_error` y decidir)
    antes de poder volver a encolarlo."""

    def __init__(self, trabajo_id: str, intentos: int, max_intentos: int):
        super().__init__(
            f"El trabajo '{trabajo_id}' ya fallo {intentos} de {max_intentos} intentos "
            "permitidos -- revise mensaje_error antes de reintentar manualmente."
        )
        self.trabajo_id = trabajo_id
        self.intentos = intentos
        self.max_intentos = max_intentos
