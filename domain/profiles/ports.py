"""Puertos (interfaces) del contexto Perfiles.

Definidos en domain e implementados en infrastructure (ADR-001, seccion
4). El repositorio de perfiles trata cada version publicada como
inmutable: una vez guardada, `save()` no puede sobrescribirla (ver
ProfileVersionAlreadyExistsError).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import PerfilProyecto


class ProfileRepository(ABC):
    """Carga y publicacion de paquetes de perfil versionados (Documento
    Maestro, seccion 4.3). La implementacion de infrastructure lee/escribe
    YAML desde /perfiles/<id>/<version>.yaml dentro de la ruta raiz
    confirmada."""

    @abstractmethod
    def get(self, perfil_id: str) -> Optional[PerfilProyecto]:
        """Devuelve la version vigente (la de version mas alta) del
        perfil, o None si el perfil no existe."""
        ...

    @abstractmethod
    def get_version(self, perfil_id: str, version: str) -> Optional[PerfilProyecto]:
        """Devuelve una version especifica del perfil, o None si esa
        version no existe."""
        ...

    @abstractmethod
    def list_versions(self, perfil_id: str) -> list[str]:
        """Devuelve las versiones publicadas del perfil, ordenadas de
        mas antigua a mas reciente."""
        ...

    @abstractmethod
    def list(self) -> list[PerfilProyecto]:
        """Devuelve la version vigente de cada perfil conocido."""
        ...

    @abstractmethod
    def save(self, perfil: PerfilProyecto) -> None:
        """Publica una nueva version de un perfil. Debe fallar (ver
        ProfileVersionAlreadyExistsError) si esa combinacion id/version
        ya fue publicada -- las versiones son inmutables."""
        ...
