"""Prueba de humo de la Fase 10 (Seguridad y distribucion). Mismo patron
que test_reportes_extremo_a_extremo.py: bootstrap()/abrir_proyecto()
reales, sin fakes, para probar el cableado completo de app.bootstrap
(SecurityService sobre KeyringCredentialStore/EncryptedZipRespaldoStore
reales) -- salvo el backend de `keyring`, sustituido por uno en memoria
(ver docstring de KeyringCredentialStore/test_keyring_credential_store.py):
un sandbox headless de pruebas no tiene sesion de escritorio real, pero
eso no cambia ni una linea del codigo de produccion que se ejercita
aqui."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import keyring
import keyring.backend
import keyring.errors
import pytest

from app.bootstrap import abrir_proyecto, bootstrap

RAIZ_PRUEBA = Path("/tmp/rag_content_studio_smoke_test_respaldo")


class _BackendEnMemoria(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self._datos: dict[tuple[str, str], str] = {}

    def set_password(self, servicename: str, username: str, password: str) -> None:
        self._datos[(servicename, username)] = password

    def get_password(self, servicename: str, username: str) -> Optional[str]:
        return self._datos.get((servicename, username))

    def delete_password(self, servicename: str, username: str) -> None:
        if (servicename, username) not in self._datos:
            raise keyring.errors.PasswordDeleteError("no existe")
        del self._datos[(servicename, username)]


@pytest.fixture()
def backend_en_memoria():
    backend_original = keyring.get_keyring()
    keyring.set_keyring(_BackendEnMemoria())
    yield
    keyring.set_keyring(backend_original)


@pytest.fixture()
def raiz_temporal():
    if RAIZ_PRUEBA.exists():
        shutil.rmtree(RAIZ_PRUEBA)
    RAIZ_PRUEBA.mkdir(parents=True)
    perfiles_dir = RAIZ_PRUEBA / "perfiles" / "perfil_generico"
    perfiles_dir.mkdir(parents=True)
    shutil.copy(
        Path(__file__).resolve().parents[2] / "perfiles" / "perfil_generico" / "0.1.yaml",
        perfiles_dir / "0.1.yaml",
    )
    yield RAIZ_PRUEBA
    shutil.rmtree(RAIZ_PRUEBA, ignore_errors=True)


def test_crear_y_restaurar_un_respaldo_real_de_un_proyecto(raiz_temporal: Path, backend_en_memoria: None) -> None:
    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Fase 10", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    archivo = Path(proyecto.ruta_carpeta) / "01_originales" / "_prueba_manual.txt"
    archivo.write_text("contenido real de prueba para el respaldo", encoding="utf-8")

    respaldo = pctx.security.crear_respaldo(proyecto.id, Path(proyecto.ruta_carpeta))
    assert Path(respaldo.ruta_archivo).exists()
    assert Path(respaldo.ruta_archivo).parent.name == "13_respaldos"

    destino = raiz_temporal / "_restaurado"
    restauracion = pctx.security.restaurar_respaldo(proyecto.id, Path(respaldo.ruta_archivo), destino)

    assert restauracion.exitosa is True
    contenido_restaurado = (destino / "01_originales" / "_prueba_manual.txt").read_text(encoding="utf-8")
    assert contenido_restaurado == "contenido real de prueba para el respaldo"


def test_restaurar_sin_haber_creado_nunca_un_respaldo_lanza_error_claro(
    raiz_temporal: Path, backend_en_memoria: None
) -> None:
    from domain.security.exceptions import ClaveDeRespaldoNoEncontradaError

    ctx = bootstrap(raiz=str(raiz_temporal))
    proyecto = ctx.projects.crear_proyecto(nombre="Fase 10 sin respaldo", perfil_id="perfil_generico")
    pctx = abrir_proyecto(ctx, proyecto)

    with pytest.raises(ClaveDeRespaldoNoEncontradaError):
        pctx.security.restaurar_respaldo(
            proyecto.id, raiz_temporal / "no_existe.zip.enc", raiz_temporal / "destino"
        )
