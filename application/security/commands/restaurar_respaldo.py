"""Caso de uso RestaurarRespaldo (Fase 10, Documento Maestro seccion 9:
"...pruebas de restauracion" -- un respaldo que nunca se probo restaurar
no esta realmente verificado, solo se asume integro por existir).

A diferencia de `CrearRespaldo` (que siempre debe tener exito o fallar
ruidosamente: un respaldo que no se creo es un respaldo que no existe),
una restauracion puede fallar de forma ESPERADA (clave incorrecta,
archivo corrupto o alterado) sin que eso sea un error de programacion --
mismo criterio de "pendiente/fallido no es un bug" que
`application.acceptance.commands.ejecutar_pruebas_aceptacion` ya aplica
para los dominios sin corpus todavia. La unica excepcion real que este
caso de uso lanza es la ausencia TOTAL de la clave en el almacen de
credenciales: sin ella no hay siquiera algo que intentar."""
from __future__ import annotations

from pathlib import Path

from domain.security.entities import RestauracionRespaldo
from domain.security.exceptions import ClaveDeRespaldoNoEncontradaError
from domain.security.ports import CredentialStore, RespaldoStore


def _nombre_clave(proyecto_id: str) -> str:
    return f"respaldo:{proyecto_id}"


class RestaurarRespaldo:
    def __init__(self, credential_store: CredentialStore, respaldo_store: RespaldoStore):
        self._credential_store = credential_store
        self._respaldo_store = respaldo_store

    def execute(self, proyecto_id: str, ruta_archivo: Path, destino: Path) -> RestauracionRespaldo:
        clave = self._credential_store.obtener_secreto(_nombre_clave(proyecto_id))
        if clave is None:
            raise ClaveDeRespaldoNoEncontradaError(proyecto_id)
        return self._respaldo_store.restaurar(ruta_archivo, clave, destino)
