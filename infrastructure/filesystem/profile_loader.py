"""Adaptador de ProfileRepository sobre archivos YAML en /perfiles/
(Documento Maestro, seccion 4.3: "Perfiles YAML o JSON").

Cada perfil vive en su propia subcarpeta y cada version publicada es un
archivo YAML independiente e inmutable:

    perfiles/<perfil_id>/<version>.yaml

La "version vigente" es la de numero mas alto (comparacion semantica
N.N, no alfabetica -- "0.10" es posterior a "0.9").
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from domain.profiles.entities import PerfilProyecto, clave_version
from domain.profiles.exceptions import ProfileVersionAlreadyExistsError
from domain.profiles.ports import ProfileRepository


class YamlProfileRepository(ProfileRepository):
    def __init__(self, perfiles_root: Path):
        self._perfiles_root = perfiles_root

    def _carpeta_perfil(self, perfil_id: str) -> Path:
        return self._perfiles_root / perfil_id

    def get(self, perfil_id: str) -> Optional[PerfilProyecto]:
        versiones = self.list_versions(perfil_id)
        if not versiones:
            return None
        return self.get_version(perfil_id, versiones[-1])

    def get_version(self, perfil_id: str, version: str) -> Optional[PerfilProyecto]:
        ruta = self._carpeta_perfil(perfil_id) / f"{version}.yaml"
        if not ruta.exists():
            return None
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        return PerfilProyecto(**datos)

    def list_versions(self, perfil_id: str) -> list[str]:
        carpeta = self._carpeta_perfil(perfil_id)
        if not carpeta.exists():
            return []
        # Hallazgo real de la cuarta auditoria general (2026-08-01): estos
        # nombres de archivo vienen directo del sistema de archivos, sin
        # pasar por la validacion de Pydantic de PerfilProyecto.version --
        # un archivo mal nombrado (copia manual, typo) hacia que la
        # ordenacion lanzara un ValueError crudo. clave_version() (domain,
        # unico lugar que hace esta conversion) traduce eso a
        # VersionDePerfilInvalidaError.
        versiones = [ruta.stem for ruta in carpeta.glob("*.yaml")]
        return sorted(versiones, key=clave_version)

    def list(self) -> list[PerfilProyecto]:
        if not self._perfiles_root.exists():
            return []
        perfiles = []
        for carpeta in sorted(p for p in self._perfiles_root.iterdir() if p.is_dir()):
            perfil = self.get(carpeta.name)
            if perfil is not None:
                perfiles.append(perfil)
        return perfiles

    def save(self, perfil: PerfilProyecto) -> None:
        carpeta = self._carpeta_perfil(perfil.id)
        ruta = carpeta / f"{perfil.version}.yaml"
        if ruta.exists():
            raise ProfileVersionAlreadyExistsError(perfil.id, perfil.version)
        carpeta.mkdir(parents=True, exist_ok=True)
        datos = perfil.model_dump(mode="json", exclude_none=False)
        ruta.write_text(
            yaml.safe_dump(datos, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
