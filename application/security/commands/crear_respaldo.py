"""Caso de uso CrearRespaldo (Fase 10, Documento Maestro seccion 9:
"Respaldos cifrados y pruebas de restauracion"; ADR-001 seccion 14.3).

La clave de cifrado se reutiliza entre respaldos sucesivos del MISMO
proyecto -- una sola clave por proyecto, no una por respaldo -- para
poder restaurar cualquier respaldo anterior del proyecto con la clave
que hoy este guardada en el almacen de credenciales, sin tener que
llevar un registro aparte de "cual clave corresponde a cual archivo".
Contrapartida documentada explicitamente en el manual de operacion: si
esa clave se pierde, todos los respaldos de ese proyecto (pasados y
futuros) quedan igual de irrecuperables (ver
`domain.security.exceptions.ClaveDeRespaldoNoEncontradaError`)."""
from __future__ import annotations

from pathlib import Path

from domain.security.entities import RespaldoProyecto
from domain.security.ports import CredentialStore, RespaldoStore


def _nombre_clave(proyecto_id: str) -> str:
    return f"respaldo:{proyecto_id}"


class CrearRespaldo:
    def __init__(self, credential_store: CredentialStore, respaldo_store: RespaldoStore):
        self._credential_store = credential_store
        self._respaldo_store = respaldo_store

    def execute(self, proyecto_id: str, carpeta_proyecto: Path) -> RespaldoProyecto:
        nombre = _nombre_clave(proyecto_id)
        clave = self._credential_store.obtener_secreto(nombre)
        if clave is None:
            clave = self._respaldo_store.generar_clave()
            self._credential_store.guardar_secreto(nombre, clave)
        return self._respaldo_store.crear(carpeta_proyecto, proyecto_id, clave)
