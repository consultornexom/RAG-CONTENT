"""Caso de uso: publicar la primera version de un perfil nuevo (Modulo
2, Documento Maestro Anexo B: "Primer perfil de proyecto").
"""
from __future__ import annotations

from domain.profiles.entities import (
    CampoMetadato,
    Catalogo,
    PerfilProyecto,
    ReglaNormalizacion,
    ReglaValidacion,
)
from domain.profiles.exceptions import ProfileVersionAlreadyExistsError
from domain.profiles.ports import ProfileRepository


class CrearPerfil:
    """Publica la version inicial ('0.1' por convencion, pero cualquier
    id.version aun no publicado es valido) de un perfil. No permite
    reutilizar un id+version ya existente -- las versiones publicadas
    son inmutables (ver PublicarNuevaVersionPerfil para evolucionarlo)."""

    def __init__(self, profiles: ProfileRepository):
        self._profiles = profiles

    def execute(
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
        if self._profiles.get_version(perfil_id, version) is not None:
            raise ProfileVersionAlreadyExistsError(perfil_id, version)

        perfil = PerfilProyecto(
            id=perfil_id,
            version=version,
            descripcion=descripcion,
            campos_metadato=campos_metadato or [],
            catalogos=catalogos or [],
            reglas_validacion=reglas_validacion or [],
            reglas_normalizacion=reglas_normalizacion or [],
            tipos_documentales_criticos=tipos_documentales_criticos or [],
            plantilla_markdown=plantilla_markdown,
            incidencias_criticas_permitidas=incidencias_criticas_permitidas,
            revision_obligatoria=revision_obligatoria,
            confirmacion_vigencia_obligatoria=confirmacion_vigencia_obligatoria,
        )
        self._profiles.save(perfil)
        return perfil
