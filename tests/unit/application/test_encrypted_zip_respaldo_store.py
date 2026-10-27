"""EncryptedZipRespaldoStore (Fase 10): sin dependencias del sistema
operativo (zipfile + cryptography puros) -- se prueba de verdad, sin
fakes, contra una carpeta de proyecto real en disco (`tmp_path`), igual
que `test_local_report_writer.py`/`test_csv_manifest_writer.py`."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from cryptography.fernet import Fernet

from infrastructure.security.encrypted_zip_respaldo_store import EncryptedZipRespaldoStore


def _crear_carpeta_de_proyecto(base: Path) -> Path:
    carpeta = base / "PROY-0001_prueba"
    (carpeta / "01_originales").mkdir(parents=True)
    (carpeta / "07_markdown").mkdir(parents=True)
    (carpeta / "01_originales" / "documento.txt").write_text("contenido original", encoding="utf-8")
    (carpeta / "07_markdown" / "documento.md").write_text("# Documento\n\nContenido.", encoding="utf-8")
    return carpeta


def test_crear_devuelve_un_respaldo_con_hash_y_tamano_reales(tmp_path: Path) -> None:
    carpeta_proyecto = _crear_carpeta_de_proyecto(tmp_path)
    store = EncryptedZipRespaldoStore()
    clave = store.generar_clave()

    respaldo = store.crear(carpeta_proyecto, "PROY-0001", clave)

    ruta_respaldo = Path(respaldo.ruta_archivo)
    assert ruta_respaldo.exists()
    assert ruta_respaldo.parent == carpeta_proyecto / "13_respaldos"
    assert respaldo.tamano_bytes == ruta_respaldo.stat().st_size
    assert respaldo.hash_sha256 == hashlib.sha256(ruta_respaldo.read_bytes()).hexdigest()


def test_crear_no_deja_ningun_zip_temporal_sin_cifrar(tmp_path: Path) -> None:
    carpeta_proyecto = _crear_carpeta_de_proyecto(tmp_path)
    store = EncryptedZipRespaldoStore()
    clave = store.generar_clave()

    store.crear(carpeta_proyecto, "PROY-0001", clave)

    # El contenido cifrado no debe ser legible como texto plano (ni
    # siquiera contener el nombre de un archivo original en claro).
    ruta_respaldo = next((carpeta_proyecto / "13_respaldos").iterdir())
    assert b"documento.txt" not in ruta_respaldo.read_bytes()
    assert b"contenido original" not in ruta_respaldo.read_bytes()


def test_restaurar_recupera_el_contenido_original_completo(tmp_path: Path) -> None:
    carpeta_proyecto = _crear_carpeta_de_proyecto(tmp_path)
    store = EncryptedZipRespaldoStore()
    clave = store.generar_clave()
    respaldo = store.crear(carpeta_proyecto, "PROY-0001", clave)

    destino = tmp_path / "restaurado"
    restauracion = store.restaurar(Path(respaldo.ruta_archivo), clave, destino)

    assert restauracion.exitosa is True
    assert (destino / "01_originales" / "documento.txt").read_text(encoding="utf-8") == "contenido original"
    assert (destino / "07_markdown" / "documento.md").read_text(encoding="utf-8") == "# Documento\n\nContenido."
    assert not (destino / "13_respaldos").exists()  # nunca se incluye a si mismo


def test_restaurar_con_clave_incorrecta_reporta_no_exitosa_sin_lanzar(tmp_path: Path) -> None:
    carpeta_proyecto = _crear_carpeta_de_proyecto(tmp_path)
    store = EncryptedZipRespaldoStore()
    clave_correcta = store.generar_clave()
    clave_incorrecta = store.generar_clave()
    respaldo = store.crear(carpeta_proyecto, "PROY-0001", clave_correcta)

    restauracion = store.restaurar(Path(respaldo.ruta_archivo), clave_incorrecta, tmp_path / "destino")

    assert restauracion.exitosa is False
    assert "clave" in restauracion.detalle.lower()


def test_restaurar_con_archivo_alterado_reporta_no_exitosa_sin_lanzar(tmp_path: Path) -> None:
    carpeta_proyecto = _crear_carpeta_de_proyecto(tmp_path)
    store = EncryptedZipRespaldoStore()
    clave = store.generar_clave()
    respaldo = store.crear(carpeta_proyecto, "PROY-0001", clave)

    ruta_respaldo = Path(respaldo.ruta_archivo)
    contenido = bytearray(ruta_respaldo.read_bytes())
    contenido[-1] ^= 0xFF
    ruta_respaldo.write_bytes(bytes(contenido))

    restauracion = store.restaurar(ruta_respaldo, clave, tmp_path / "destino")

    assert restauracion.exitosa is False


def test_crear_no_incluye_respaldos_anteriores_en_el_zip_nuevo(tmp_path: Path) -> None:
    carpeta_proyecto = _crear_carpeta_de_proyecto(tmp_path)
    store = EncryptedZipRespaldoStore()
    clave = store.generar_clave()

    primer_respaldo = store.crear(carpeta_proyecto, "PROY-0001", clave)
    assert Path(primer_respaldo.ruta_archivo).exists()

    segundo_respaldo = store.crear(carpeta_proyecto, "PROY-0001", clave)
    destino = tmp_path / "restaurado"
    restauracion = store.restaurar(Path(segundo_respaldo.ruta_archivo), clave, destino)

    assert restauracion.exitosa is True
    # El segundo respaldo no debe contener, dentro de si mismo, el
    # primero -- si lo incluyera, "13_respaldos" apareceria dentro de la
    # carpeta restaurada.
    assert not (destino / "13_respaldos").exists()


def test_restaurar_detecta_un_zip_con_ruta_fuera_del_destino(tmp_path: Path) -> None:
    """"Zip slip": un zip (cifrado con la clave real) cuyo contenido
    intenta escribir fuera de la carpeta de destino debe reportarse como
    no exitoso, nunca extraerse."""
    zip_malicioso = tmp_path / "malicioso.zip"
    with zipfile.ZipFile(zip_malicioso, "w") as zf:
        zf.writestr("../../fuera_del_destino.txt", "contenido que no deberia escapar")

    store = EncryptedZipRespaldoStore()
    clave = store.generar_clave()
    fernet = Fernet(clave.encode("ascii"))
    ruta_cifrada = tmp_path / "malicioso.zip.enc"
    ruta_cifrada.write_bytes(fernet.encrypt(zip_malicioso.read_bytes()))

    destino = tmp_path / "destino"
    restauracion = store.restaurar(ruta_cifrada, clave, destino)

    assert restauracion.exitosa is False
    assert "ruta invalida" in restauracion.detalle.lower()
    assert not (tmp_path / "fuera_del_destino.txt").exists()
