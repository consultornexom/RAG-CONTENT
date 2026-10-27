"""CrearRespaldo (Fase 10): fachadas falsas de CredentialStore/
RespaldoStore en memoria -- mismo criterio de prueba que
`test_ejecutar_pruebas_aceptacion.py` (fakes que reutilizan el
comportamiento real esperado del puerto, sin `unittest.mock`)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from application.security.commands.crear_respaldo import CrearRespaldo
from domain.security.entities import RespaldoProyecto, RestauracionRespaldo


class _FakeCredentialStore:
    def __init__(self) -> None:
        self._secretos: dict[str, str] = {}

    def guardar_secreto(self, nombre: str, valor: str) -> None:
        self._secretos[nombre] = valor

    def obtener_secreto(self, nombre: str) -> Optional[str]:
        return self._secretos.get(nombre)

    def eliminar_secreto(self, nombre: str) -> None:
        self._secretos.pop(nombre, None)


class _FakeRespaldoStore:
    def __init__(self) -> None:
        self.claves_usadas: list[str] = []
        self.contador = 0

    def generar_clave(self) -> str:
        return "clave-generada-de-prueba"

    def crear(self, carpeta_proyecto: Path, proyecto_id: str, clave: str) -> RespaldoProyecto:
        self.claves_usadas.append(clave)
        self.contador += 1
        return RespaldoProyecto(
            proyecto_id=proyecto_id,
            ruta_archivo=str(carpeta_proyecto / f"13_respaldos/respaldo_{self.contador}.zip.enc"),
            hash_sha256="a" * 64,
            tamano_bytes=100,
        )

    def restaurar(self, ruta_archivo: Path, clave: str, destino: Path) -> RestauracionRespaldo:
        raise NotImplementedError("no usado en estas pruebas")


def test_crea_una_clave_nueva_cuando_no_existe_ninguna(tmp_path: Path) -> None:
    credential_store = _FakeCredentialStore()
    respaldo_store = _FakeRespaldoStore()
    caso_de_uso = CrearRespaldo(credential_store, respaldo_store)

    respaldo = caso_de_uso.execute("PROY-0001", tmp_path)

    assert respaldo.proyecto_id == "PROY-0001"
    assert credential_store.obtener_secreto("respaldo:PROY-0001") == "clave-generada-de-prueba"
    assert respaldo_store.claves_usadas == ["clave-generada-de-prueba"]


def test_reutiliza_la_clave_existente_en_respaldos_sucesivos(tmp_path: Path) -> None:
    credential_store = _FakeCredentialStore()
    credential_store.guardar_secreto("respaldo:PROY-0001", "clave-ya-guardada")
    respaldo_store = _FakeRespaldoStore()
    caso_de_uso = CrearRespaldo(credential_store, respaldo_store)

    caso_de_uso.execute("PROY-0001", tmp_path)
    caso_de_uso.execute("PROY-0001", tmp_path)

    assert respaldo_store.claves_usadas == ["clave-ya-guardada", "clave-ya-guardada"]
    assert credential_store.obtener_secreto("respaldo:PROY-0001") == "clave-ya-guardada"
