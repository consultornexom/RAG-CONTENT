"""Caso de uso: comparar dos versiones publicadas de un perfil (Modulo
2). Util antes de aplicar una version nueva a un proyecto existente --
muestra que campos de metadato, catalogos o reglas cambiaron."""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.profiles.exceptions import ProfileNotFoundError
from domain.profiles.ports import ProfileRepository


@dataclass
class ComparacionPerfil:
    perfil_id: str
    version_base: str
    version_nueva: str
    campos_agregados: list[str] = field(default_factory=list)
    campos_eliminados: list[str] = field(default_factory=list)
    campos_modificados: list[str] = field(default_factory=list)
    catalogos_agregados: list[str] = field(default_factory=list)
    catalogos_eliminados: list[str] = field(default_factory=list)
    reglas_agregadas: list[str] = field(default_factory=list)
    reglas_eliminadas: list[str] = field(default_factory=list)

    @property
    def hay_cambios_incompatibles(self) -> bool:
        """Un campo obligatorio eliminado o un catalogo eliminado puede
        romper metadatos ya capturados con la version anterior -- se
        marca para que la UI lo destaque, sin bloquear la comparacion."""
        return bool(self.campos_eliminados or self.catalogos_eliminados)


class CompararVersionesPerfil:
    def __init__(self, profiles: ProfileRepository):
        self._profiles = profiles

    def execute(self, perfil_id: str, version_base: str, version_nueva: str) -> ComparacionPerfil:
        base = self._profiles.get_version(perfil_id, version_base)
        if base is None:
            raise ProfileNotFoundError(perfil_id, version_base)

        nueva = self._profiles.get_version(perfil_id, version_nueva)
        if nueva is None:
            raise ProfileNotFoundError(perfil_id, version_nueva)

        campos_base = {c.field_id: c for c in base.campos_metadato}
        campos_nuevos = {c.field_id: c for c in nueva.campos_metadato}

        campos_agregados = sorted(set(campos_nuevos) - set(campos_base))
        campos_eliminados = sorted(set(campos_base) - set(campos_nuevos))
        campos_modificados = sorted(
            field_id
            for field_id in set(campos_base) & set(campos_nuevos)
            if campos_base[field_id] != campos_nuevos[field_id]
        )

        catalogos_base = {c.nombre for c in base.catalogos}
        catalogos_nuevos = {c.nombre for c in nueva.catalogos}

        reglas_base = {(r.field_id, r.tipo_regla) for r in base.reglas_validacion}
        reglas_nuevas = {(r.field_id, r.tipo_regla) for r in nueva.reglas_validacion}

        return ComparacionPerfil(
            perfil_id=perfil_id,
            version_base=version_base,
            version_nueva=version_nueva,
            campos_agregados=campos_agregados,
            campos_eliminados=campos_eliminados,
            campos_modificados=campos_modificados,
            catalogos_agregados=sorted(catalogos_nuevos - catalogos_base),
            catalogos_eliminados=sorted(catalogos_base - catalogos_nuevos),
            reglas_agregadas=sorted(f"{fid}:{tipo}" for fid, tipo in reglas_nuevas - reglas_base),
            reglas_eliminadas=sorted(f"{fid}:{tipo}" for fid, tipo in reglas_base - reglas_nuevas),
        )
