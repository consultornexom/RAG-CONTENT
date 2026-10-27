"""Fachada del contexto Perfiles (ADR-001, seccion 4: ui solo depende de
application)."""
from __future__ import annotations

from domain.profiles.entities import (
    CampoMetadato,
    Catalogo,
    PerfilProyecto,
    ReglaNormalizacion,
    ReglaValidacion,
)
from domain.profiles.ports import ProfileRepository

from .commands.comparar_versiones import ComparacionPerfil, CompararVersionesPerfil
from .commands.crear_perfil import CrearPerfil
from .commands.publicar_nueva_version import PublicarNuevaVersionPerfil


class ProfilesService:
    def __init__(self, profiles: ProfileRepository):
        self._profiles = profiles
        self._crear = CrearPerfil(profiles)
        self._publicar = PublicarNuevaVersionPerfil(profiles)
        self._comparar = CompararVersionesPerfil(profiles)

    def crear_perfil(
        self,
        perfil_id: str,
        version: str = "0.1",
        descripcion: str = "",
        campos_metadato: list[CampoMetadato] | None = None,
        catalogos: list[Catalogo] | None = None,
        reglas_validacion: list[ReglaValidacion] | None = None,
        reglas_normalizacion: list[ReglaNormalizacion] | None = None,
        tipos_documentales_criticos: list[str] | None = None,
        plantilla_markdown: str | None = None,
        incidencias_criticas_permitidas: int = 0,
        revision_obligatoria: bool = True,
        confirmacion_vigencia_obligatoria: bool = True,
    ) -> PerfilProyecto:
        return self._crear.execute(
            perfil_id=perfil_id,
            version=version,
            descripcion=descripcion,
            campos_metadato=campos_metadato,
            catalogos=catalogos,
            reglas_validacion=reglas_validacion,
            reglas_normalizacion=reglas_normalizacion,
            tipos_documentales_criticos=tipos_documentales_criticos,
            plantilla_markdown=plantilla_markdown,
            incidencias_criticas_permitidas=incidencias_criticas_permitidas,
            revision_obligatoria=revision_obligatoria,
            confirmacion_vigencia_obligatoria=confirmacion_vigencia_obligatoria,
        )

    def publicar_nueva_version(self, perfil_id: str, nueva_version: PerfilProyecto) -> PerfilProyecto:
        return self._publicar.execute(perfil_id, nueva_version)

    def comparar_versiones(
        self, perfil_id: str, version_base: str, version_nueva: str
    ) -> ComparacionPerfil:
        return self._comparar.execute(perfil_id, version_base, version_nueva)

    def obtener_perfil(self, perfil_id: str) -> PerfilProyecto | None:
        return self._profiles.get(perfil_id)

    def obtener_version(self, perfil_id: str, version: str) -> PerfilProyecto | None:
        return self._profiles.get_version(perfil_id, version)

    def listar_perfiles(self) -> list[PerfilProyecto]:
        return self._profiles.list()

    def listar_versiones(self, perfil_id: str) -> list[str]:
        return self._profiles.list_versions(perfil_id)
