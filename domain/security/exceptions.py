"""Excepciones del contexto Seguridad (Fase 10)."""
from __future__ import annotations


class SecurityDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class ClaveDeRespaldoNoEncontradaError(SecurityDomainError):
    """No hay clave de cifrado guardada en el almacen de credenciales
    para este proyecto -- no se puede restaurar ninguno de sus respaldos
    (ni crear uno nuevo reutilizando la clave existente) sin ella. No
    existe ningun mecanismo de recuperacion de clave perdida en esta
    version (ADR-001, seccion 14.3): perder el acceso al almacen de
    credenciales del sistema operativo significa perder el acceso a
    todos los respaldos cifrados de ese proyecto por igual -- documentado
    explicitamente en el manual de operacion, no una omision."""

    def __init__(self, proyecto_id: str):
        super().__init__(
            f"No se encontro una clave de cifrado de respaldos para el proyecto '{proyecto_id}' "
            "en el almacen de credenciales del sistema operativo."
        )
        self.proyecto_id = proyecto_id
