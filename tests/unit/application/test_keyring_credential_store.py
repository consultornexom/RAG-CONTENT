"""KeyringCredentialStore (Fase 10): ejercita el codigo real del
adaptador (llamadas reales a `keyring.set_password`/`get_password`/
`delete_password`) contra un backend en memoria propio de este archivo
de pruebas -- un sandbox headless de pruebas no tiene sesion de
escritorio (`keyring.errors.NoKeyringError` con el backend por defecto),
pero eso es una limitacion de QUE backend hay disponible, no del
adaptador en si (ver el docstring de `KeyringCredentialStore`). En
produccion `keyring` elige un backend real del sistema operativo por su
cuenta; aqui se sustituye explicitamente solo esa eleccion."""
from __future__ import annotations

from typing import Optional

import keyring
import keyring.backend
import keyring.errors
import pytest

from infrastructure.security.keyring_credential_store import KeyringCredentialStore


class _BackendEnMemoria(keyring.backend.KeyringBackend):
    """Backend minimo, solo para pruebas: un diccionario en memoria en
    vez de un almacen de credenciales real del sistema operativo."""

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
            raise keyring.errors.PasswordDeleteError(f"No existe ninguna contrasena para {servicename}/{username}")
        del self._datos[(servicename, username)]


@pytest.fixture()
def backend_en_memoria():
    backend_original = keyring.get_keyring()
    keyring.set_keyring(_BackendEnMemoria())
    yield
    keyring.set_keyring(backend_original)


def test_guardar_y_obtener_secreto(backend_en_memoria: None) -> None:
    store = KeyringCredentialStore()

    store.guardar_secreto("respaldo:PROY-0001", "clave-super-secreta")

    assert store.obtener_secreto("respaldo:PROY-0001") == "clave-super-secreta"


def test_obtener_secreto_inexistente_devuelve_none(backend_en_memoria: None) -> None:
    store = KeyringCredentialStore()

    assert store.obtener_secreto("respaldo:no-existe") is None


def test_eliminar_secreto_existente(backend_en_memoria: None) -> None:
    store = KeyringCredentialStore()
    store.guardar_secreto("respaldo:PROY-0002", "otra-clave")

    store.eliminar_secreto("respaldo:PROY-0002")

    assert store.obtener_secreto("respaldo:PROY-0002") is None


def test_eliminar_secreto_inexistente_no_lanza_excepcion(backend_en_memoria: None) -> None:
    store = KeyringCredentialStore()

    store.eliminar_secreto("respaldo:jamas-existio")  # no debe lanzar nada
