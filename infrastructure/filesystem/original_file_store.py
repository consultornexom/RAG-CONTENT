"""Adaptador de OriginalFileStore sobre el sistema de archivos local
(ADR-001, seccion 4). Copia el archivo original a 01_originales/ del
proyecto (Documento Maestro, seccion 4.5) y calcula su hash SHA-256.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from domain.documents.exceptions import OriginalFileCopyError, SourceFileNotFoundError
from domain.documents.ports import OriginalFileStore

_TAMANO_BLOQUE = 1024 * 1024  # 1 MiB por lectura -- evita cargar archivos grandes completos en memoria.


def _hash_sha256_de(ruta: Path) -> str:
    hasher = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(_TAMANO_BLOQUE), b""):
            hasher.update(bloque)
    return hasher.hexdigest()


class LocalOriginalFileStore(OriginalFileStore):
    def __init__(self, carpeta_originales: Path):
        self._carpeta_originales = carpeta_originales

    def copiar_original(self, ruta_origen: str) -> tuple[str, str, int]:
        origen = Path(ruta_origen)
        if not origen.is_file():
            raise SourceFileNotFoundError(ruta_origen)

        hash_sha256 = _hash_sha256_de(origen)
        nombre_destino = f"{hash_sha256[:12]}_{origen.name}"
        destino = self._carpeta_originales / nombre_destino

        if destino.exists():
            # Reintento de un registro previo (o el mismo archivo ya
            # copiado): el nombre incluye el hash, asi que si el
            # archivo ya existe con ese nombre es, por construccion,
            # el mismo contenido -- no hace falta volver a copiarlo.
            return str(destino), hash_sha256, destino.stat().st_size

        try:
            self._carpeta_originales.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
        except OSError as exc:
            if destino.exists():
                destino.unlink(missing_ok=True)
            raise OriginalFileCopyError(ruta_origen, str(exc)) from exc

        return str(destino), hash_sha256, destino.stat().st_size
