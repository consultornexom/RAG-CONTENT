"""Conversion DOC->DOCX y XLS->XLSX via LibreOffice headless. RAG
STUDIO no tiene este adaptador (no maneja formatos legado) -- es propio
de RAG Content Studio Desktop (ADR-001, seccion 8, fila
DocumentExtractor). Cada llamada usa un perfil de usuario de LibreOffice
temporal y exclusivo (`-env:UserInstallation`) para evitar el error
real "User installation could not be completed"/bloqueos de perfil
compartido entre ejecuciones concurrentes -- confirmado empiricamente
que este entorno soporta sockets AF_UNIX sin necesitar ningun shim
adicional (a diferencia de otros entornos sandbox mas restrictivos).
"""
from __future__ import annotations

import shutil

# Se invoca "soffice" con una lista de argumentos (shell=False, nunca
# shell=True) y con la ruta absoluta resuelta por shutil.which() en vez
# de un nombre parcial -- Bandit B404/B603/B607 son advertencias
# esperadas para cualquier uso de subprocess, incluso ya mitigado asi.
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from domain.documents.entities import FormatoDocumento
from domain.documents.exceptions import LegacyConversionFailedError
from domain.documents.ports import LegacyFormatConverter

_FILTRO_POR_FORMATO_DESTINO = {
    FormatoDocumento.DOCX: "docx",
    FormatoDocumento.XLSX: "xlsx",
}
_TIMEOUT_SEGUNDOS = 120


class LibreOfficeConverter(LegacyFormatConverter):
    def convertir(self, ruta: str, formato_destino: FormatoDocumento) -> str:
        filtro = _FILTRO_POR_FORMATO_DESTINO.get(formato_destino)
        if filtro is None:
            raise LegacyConversionFailedError(
                ruta, f"Formato de destino no soportado para conversion: {formato_destino.value!r}"
            )
        # Ruta absoluta resuelta aqui (no un nombre parcial "soffice"
        # dejado a merced del PATH en tiempo de ejecucion del subproceso).
        ruta_soffice = shutil.which("soffice")
        if ruta_soffice is None:
            raise LegacyConversionFailedError(
                ruta, "El binario 'soffice' (LibreOffice) no esta instalado en este sistema operativo."
            )

        directorio_salida = tempfile.mkdtemp(prefix="rag_content_studio_legacy_")
        perfil_temporal = tempfile.mkdtemp(prefix="rag_content_studio_lo_profile_")
        try:
            resultado = subprocess.run(  # nosec B603
                [
                    ruta_soffice,
                    "--headless",
                    "--norestore",
                    f"-env:UserInstallation=file://{perfil_temporal}",
                    "--convert-to",
                    filtro,
                    "--outdir",
                    directorio_salida,
                    ruta,
                ],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SEGUNDOS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(directorio_salida, ignore_errors=True)
            raise LegacyConversionFailedError(
                ruta, f"LibreOffice no respondio en {_TIMEOUT_SEGUNDOS} segundos."
            ) from exc
        finally:
            shutil.rmtree(perfil_temporal, ignore_errors=True)

        ruta_destino = Path(directorio_salida) / f"{Path(ruta).stem}.{filtro}"
        if resultado.returncode != 0 or not ruta_destino.exists():
            shutil.rmtree(directorio_salida, ignore_errors=True)
            detalle = resultado.stderr.strip() or resultado.stdout.strip() or "sin salida de diagnostico del subproceso"
            raise LegacyConversionFailedError(ruta, f"LibreOffice no pudo convertir el archivo: {detalle}")

        return str(ruta_destino)
