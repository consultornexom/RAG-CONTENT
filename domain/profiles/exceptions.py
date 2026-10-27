"""Excepciones del contexto Perfiles."""
from __future__ import annotations


class ProfileDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class ProfileVersionAlreadyExistsError(ProfileDomainError):
    """Una version de perfil publicada es inmutable: no se puede volver
    a guardar con el mismo id+version (Documento Maestro, seccion 4.3)."""

    def __init__(self, perfil_id: str, version: str):
        super().__init__(
            f"La version '{version}' del perfil '{perfil_id}' ya fue publicada y es "
            "inmutable. Publique una version nueva (por ejemplo, incrementando el numero "
            "menor) en lugar de sobrescribir esta."
        )
        self.perfil_id = perfil_id
        self.version = version


class ProfileNotFoundError(ProfileDomainError):
    """El perfil (o la version solicitada) no existe todavia."""

    def __init__(self, perfil_id: str, version: str | None = None):
        if version:
            mensaje = f"No se encontro la version '{version}' del perfil '{perfil_id}'."
        else:
            mensaje = f"No se encontro el perfil '{perfil_id}'."
        super().__init__(mensaje)
        self.perfil_id = perfil_id
        self.version = version


class VersionDePerfilInvalidaError(ProfileDomainError):
    """Hallazgo real de la cuarta auditoria general (2026-08-01): una
    version de perfil que no sigue el formato 'N.N' (por ejemplo, un
    archivo YAML mal nombrado en `perfiles/<id>/` -- copia manual, typo,
    version con tres numeros) hacia que `_clave_version()` (duplicada en
    `application.profiles.commands.publicar_nueva_version` e
    `infrastructure.filesystem.profile_loader`) lanzara un `ValueError`
    nativo de Python al hacer `version.split(".")`/`int(...)`, en vez de
    una excepcion de dominio -- la UI lo mostraba tal cual al usuario, un
    texto tecnico sin ninguna accion clara. Ver
    `domain.profiles.entities.clave_version()`, el unico lugar que ahora
    hace esta conversion."""

    def __init__(self, version: str):
        super().__init__(
            f"La version de perfil '{version}' no sigue el formato 'N.N' (por ejemplo, "
            "'1.0' o '2.3') -- revise el nombre del archivo YAML del perfil."
        )
        self.version = version
