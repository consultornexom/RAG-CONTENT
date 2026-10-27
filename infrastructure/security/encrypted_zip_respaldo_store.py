"""Adaptador de RespaldoStore: empaqueta la carpeta completa de un
proyecto en un zip y lo cifra con Fernet -- cifrado simetrico autenticado
de la libreria `cryptography` (ADR-001, seccion 14.3) --, guardandolo
dentro de `13_respaldos/` del propio proyecto (Documento Maestro,
seccion 4.5, carpeta reservada desde la Fase 1, sin uso real hasta esta
fase).

Excluye `13_respaldos/` del propio contenido empaquetado: un respaldo no
debe incluir respaldos anteriores (evita crecimiento recursivo entre
corridas sucesivas).

El zip intermedio (creado durante `crear()`, o el que resulta de
descifrar durante `restaurar()`) contiene el contenido COMPLETO de un
proyecto en texto claro -- es el unico archivo de toda esta herramienta
con ese nivel de sensibilidad fuera de la carpeta original del proyecto
(a diferencia de, por ejemplo, los directorios temporales de
`infrastructure.extraction.libreoffice_converter`, que no tienen
contenido confidencial propio y por eso se borran con un simple
`shutil.rmtree`). Por eso aqui se sobrescribe con bytes aleatorios antes
de eliminarlo (ADR-001, seccion 14.3: "Borrado de temporales... de forma
segura"), no solo se libera la entrada del sistema de archivos."""
from __future__ import annotations

import hashlib
import os
import secrets
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from domain.security.entities import RespaldoProyecto, RestauracionRespaldo
from domain.security.ports import RespaldoStore

_CARPETA_EXCLUIDA = "13_respaldos"


def _borrar_de_forma_segura(ruta: Path) -> None:
    """Sobrescribe el archivo entero con bytes aleatorios (y fuerza el
    `fsync` para que la sobrescritura llegue a disco, no solo a la cache
    de escritura del sistema operativo) antes de eliminarlo. No pretende
    ser un borrado forense a prueba de recuperacion de bajo nivel en
    cualquier tipo de almacenamiento (fuera del alcance de esta version,
    ADR-001 seccion 14.2: SSD sin garantia de sobrescritura fisica por
    bloque) -- si el archivo ya no existe, no hace nada (llamado siempre
    desde un `finally`, incluso cuando el paso anterior fallo antes de
    llegar a crear el archivo)."""
    if not ruta.exists():
        return
    tamano = ruta.stat().st_size
    with open(ruta, "r+b") as archivo:
        archivo.write(secrets.token_bytes(tamano))
        archivo.flush()
        os.fsync(archivo.fileno())
    ruta.unlink()


def _crear_zip_temporal(prefijo: str) -> Path:
    descriptor, ruta_str = tempfile.mkstemp(prefix=prefijo, suffix=".zip")
    os.close(descriptor)
    return Path(ruta_str)


class EncryptedZipRespaldoStore(RespaldoStore):
    def generar_clave(self) -> str:
        return Fernet.generate_key().decode("ascii")

    def crear(self, carpeta_proyecto: Path, proyecto_id: str, clave: str) -> RespaldoProyecto:
        zip_temporal = _crear_zip_temporal("rag_content_studio_respaldo_")
        try:
            with zipfile.ZipFile(zip_temporal, "w", zipfile.ZIP_DEFLATED) as zf:
                for ruta in carpeta_proyecto.rglob("*"):
                    if ruta.is_dir():
                        continue
                    relativa = ruta.relative_to(carpeta_proyecto)
                    if relativa.parts and relativa.parts[0] == _CARPETA_EXCLUIDA:
                        continue
                    zf.write(ruta, arcname=str(relativa))

            carpeta_respaldos = carpeta_proyecto / _CARPETA_EXCLUIDA
            carpeta_respaldos.mkdir(parents=True, exist_ok=True)
            fecha = datetime.now(timezone.utc)
            ruta_destino = carpeta_respaldos / f"respaldo_{fecha.strftime('%Y%m%dT%H%M%S')}.zip.enc"

            fernet = Fernet(clave.encode("ascii"))
            ruta_destino.write_bytes(fernet.encrypt(zip_temporal.read_bytes()))
        finally:
            _borrar_de_forma_segura(zip_temporal)

        contenido_cifrado = ruta_destino.read_bytes()
        return RespaldoProyecto(
            proyecto_id=proyecto_id,
            ruta_archivo=str(ruta_destino),
            hash_sha256=hashlib.sha256(contenido_cifrado).hexdigest(),
            tamano_bytes=len(contenido_cifrado),
            fecha=fecha.isoformat(),
        )

    def restaurar(self, ruta_archivo: Path, clave: str, destino: Path) -> RestauracionRespaldo:
        fernet = Fernet(clave.encode("ascii"))
        try:
            contenido_descifrado = fernet.decrypt(ruta_archivo.read_bytes())
        except InvalidToken:
            return RestauracionRespaldo(
                ruta_archivo=str(ruta_archivo),
                ruta_destino=str(destino),
                exitosa=False,
                detalle="La clave no corresponde a este archivo, o el archivo fue alterado despues de cifrarse.",
            )

        zip_temporal = _crear_zip_temporal("rag_content_studio_restauracion_")
        try:
            zip_temporal.write_bytes(contenido_descifrado)
            destino.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_temporal, "r") as zf:
                destino_resuelto = destino.resolve()
                for miembro in zf.infolist():
                    ruta_miembro = (destino / miembro.filename).resolve()
                    if ruta_miembro != destino_resuelto and destino_resuelto not in ruta_miembro.parents:
                        # "Zip slip": el zip descifrado contiene una ruta
                        # que escaparia de `destino` (por ejemplo
                        # "../../etc/algo"). Nunca deberia ocurrir con un
                        # zip creado por `crear()` (arcname siempre
                        # relativo, sin ".."), pero se verifica de forma
                        # explicita antes de extraer en vez de confiar en
                        # que el archivo cifrado no fue reemplazado por
                        # otro con el mismo nombre -- mismo criterio de
                        # "reportar, no asumir" que el resto de este
                        # metodo.
                        return RestauracionRespaldo(
                            ruta_archivo=str(ruta_archivo),
                            ruta_destino=str(destino),
                            exitosa=False,
                            detalle=(
                                f"El respaldo contiene una ruta invalida ('{miembro.filename}') "
                                "que escaparia de la carpeta de destino."
                            ),
                        )
                zf.extractall(destino)
        finally:
            _borrar_de_forma_segura(zip_temporal)

        return RestauracionRespaldo(ruta_archivo=str(ruta_archivo), ruta_destino=str(destino), exitosa=True)
