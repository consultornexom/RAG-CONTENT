"""Fachada del contexto Seguridad (ADR-001, seccion 4: ui solo depende de
application). Documento Maestro, seccion 9: "Respaldos cifrados y
pruebas de restauracion" -- los dos unicos verbos de este contexto en
esta version."""
from __future__ import annotations

from pathlib import Path

from domain.security.entities import RespaldoProyecto, RestauracionRespaldo
from domain.security.ports import CredentialStore, RespaldoStore

from .commands.crear_respaldo import CrearRespaldo
from .commands.restaurar_respaldo import RestaurarRespaldo


class SecurityService:
    def __init__(self, credential_store: CredentialStore, respaldo_store: RespaldoStore):
        self._crear = CrearRespaldo(credential_store, respaldo_store)
        self._restaurar = RestaurarRespaldo(credential_store, respaldo_store)

    def crear_respaldo(self, proyecto_id: str, carpeta_proyecto: Path) -> RespaldoProyecto:
        return self._crear.execute(proyecto_id, carpeta_proyecto)

    def restaurar_respaldo(self, proyecto_id: str, ruta_archivo: Path, destino: Path) -> RestauracionRespaldo:
        return self._restaurar.execute(proyecto_id, ruta_archivo, destino)
