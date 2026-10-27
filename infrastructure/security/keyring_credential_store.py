"""Adaptador de CredentialStore sobre `keyring` (ADR-001, seccion 14.1:
"mismo puerto y mismo adaptador (KeyringCredentialStore) que RAG
STUDIO"). Delega en el almacen de credenciales del sistema operativo
(Secret Service/GNOME Keyring o KWallet en Linux, Credential Manager en
Windows, Keychain en macOS) -- nunca escribe la clave a un archivo
propio de la aplicacion ni a ningun log (ADR-001, seccion 14.3: "Registro
de secretos: prohibido registrar secretos en logs tecnicos").

En produccion, `keyring` elige automaticamente el backend real del
sistema operativo (Secret Service/GNOME Keyring o KWallet en Linux,
Credential Manager en Windows, Keychain en macOS) -- ninguna linea de
este adaptador depende de cual sea. Un sandbox headless de pruebas sin
sesion de escritorio no tiene ese backend disponible
(`keyring.errors.NoKeyringError`); por eso
`tests/unit/infrastructure/test_keyring_credential_store.py` instala un
backend en memoria propio del archivo de pruebas via
`keyring.set_keyring()` (restaurado al final con un fixture) -- ejercita
el mismo codigo de este adaptador de verdad (set/get/delete reales contra
la API de `keyring`), sustituyendo solo la eleccion de backend que en
produccion hace `keyring` por su cuenta, nunca fingiendo el adaptador en
si."""
from __future__ import annotations

from typing import Optional

import keyring
import keyring.errors

from domain.security.ports import CredentialStore

_SERVICIO = "rag_content_studio_desktop"
"""Namespace unico de esta aplicacion dentro del almacen de credenciales
del sistema operativo -- nunca comparte entradas con RAG STUDIO ni con
ninguna otra aplicacion, aunque use el mismo mecanismo (keyring)."""


class KeyringCredentialStore(CredentialStore):
    def guardar_secreto(self, nombre: str, valor: str) -> None:
        keyring.set_password(_SERVICIO, nombre, valor)

    def obtener_secreto(self, nombre: str) -> Optional[str]:
        return keyring.get_password(_SERVICIO, nombre)

    def eliminar_secreto(self, nombre: str) -> None:
        try:
            keyring.delete_password(_SERVICIO, nombre)
        except keyring.errors.PasswordDeleteError:
            pass  # Ya no existia -- eliminar es idempotente.
