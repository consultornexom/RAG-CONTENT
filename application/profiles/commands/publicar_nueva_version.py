"""Caso de uso: publicar una nueva version de un perfil existente
(Modulo 2). Nunca modifica la version anterior -- la deja intacta en
disco y agrega una version nueva al lado (Documento Maestro, seccion
4.3)."""
from __future__ import annotations

from domain.profiles.entities import PerfilProyecto, clave_version
from domain.profiles.exceptions import ProfileNotFoundError, ProfileVersionAlreadyExistsError
from domain.profiles.ports import ProfileRepository


class PublicarNuevaVersionPerfil:
    def __init__(self, profiles: ProfileRepository):
        self._profiles = profiles

    def execute(self, perfil_id: str, nueva_version: PerfilProyecto) -> PerfilProyecto:
        if nueva_version.id != perfil_id:
            raise ValueError(
                f"El id del perfil nuevo ('{nueva_version.id}') no coincide con "
                f"'{perfil_id}'."
            )

        versiones_previas = self._profiles.list_versions(perfil_id)
        if not versiones_previas:
            raise ProfileNotFoundError(perfil_id)

        version_vigente = versiones_previas[-1]
        # Hallazgo real de la cuarta auditoria general (2026-08-01): esta
        # comparacion ahora reusa domain.profiles.entities.clave_version()
        # en vez de una funcion local duplicada -- ver su docstring para
        # el porque (excepcion de dominio en vez de ValueError crudo).
        if clave_version(nueva_version.version) <= clave_version(version_vigente):
            raise ValueError(
                f"La nueva version ('{nueva_version.version}') debe ser posterior a la "
                f"version vigente ('{version_vigente}') del perfil '{perfil_id}'."
            )

        if self._profiles.get_version(perfil_id, nueva_version.version) is not None:
            raise ProfileVersionAlreadyExistsError(perfil_id, nueva_version.version)

        self._profiles.save(nueva_version)
        return nueva_version
