"""RestaurarRespaldo (Fase 10): mismo criterio de fakes que
test_crear_respaldo.py."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from application.security.commands.restaurar_respaldo import RestaurarRespaldo
from domain.security.entities import RespaldoProyecto, RestauracionRespaldo
from domain.security.exceptions import ClaveDeRespaldoNoEncontradaError


class _FakeCredentialStore:
    def __init__(self, secretos: Optional[dict[str, str]] = None) -> None:
        self._secretos = dict(secretos or {})

    def guardar_secreto(self, nombre: str, valor: str) -> None:
        self._secretos[nombre] = valor

    def obtener_secreto(self, nombre: str) -> Optional[str]:
        return self._secretos.get(nombre)

    def eliminar_secreto(self, nombre: str) -> None:
        self._secretos.pop(nombre, None)


class _FakeRespaldoStore:
    def __init__(self, resultado: RestauracionRespaldo) -> None:
        self._resultado = resultado
        self.clave_recibida: Optional[str] = None

    def generar_clave(self) -> str:
        raise NotImplementedError("no usado en estas pruebas")

    def crear(self, carpeta_proyecto: Path, proyecto_id: str, clave: str) -> RespaldoProyecto:
        raise NotImplementedError("no usado en estas pruebas")

    def restaurar(self, ruta_archivo: Path, clave: str, destino: Path) -> RestauracionRespaldo:
        self.clave_recibida = clave
        return self._resultado


def test_lanza_error_si_no_hay_clave_guardada(tmp_path: Path) -> None:
    credential_store = _FakeCredentialStore()
    respaldo_store = _FakeRespaldoStore(
        RestauracionRespaldo(ruta_archivo="x", ruta_destino="y", exitosa=True)
    )
    caso_de_uso = RestaurarRespaldo(credential_store, respaldo_store)

    with pytest.raises(ClaveDeRespaldoNoEncontradaError) as excinfo:
        caso_de_uso.execute("PROY-0001", tmp_path / "respaldo.zip.enc", tmp_path / "destino")

    assert excinfo.value.proyecto_id == "PROY-0001"


def test_usa_la_clave_guardada_y_devuelve_el_resultado_del_store(tmp_path: Path) -> None:
    credential_store = _FakeCredentialStore({"respaldo:PROY-0001": "clave-real"})
    resultado_esperado = RestauracionRespaldo(ruta_archivo="x", ruta_destino="y", exitosa=True)
    respaldo_store = _FakeRespaldoStore(resultado_esperado)
    caso_de_uso = RestaurarRespaldo(credential_store, respaldo_store)

    resultado = caso_de_uso.execute("PROY-0001", tmp_path / "respaldo.zip.enc", tmp_path / "destino")

    assert resultado is resultado_esperado
    assert respaldo_store.clave_recibida == "clave-real"


def test_propaga_una_restauracion_no_exitosa_sin_lanzar_excepcion(tmp_path: Path) -> None:
    credential_store = _FakeCredentialStore({"respaldo:PROY-0001": "clave-real"})
    resultado_esperado = RestauracionRespaldo(
        ruta_archivo="x", ruta_destino="y", exitosa=False, detalle="clave incorrecta"
    )
    respaldo_store = _FakeRespaldoStore(resultado_esperado)
    caso_de_uso = RestaurarRespaldo(credential_store, respaldo_store)

    resultado = caso_de_uso.execute("PROY-0001", tmp_path / "respaldo.zip.enc", tmp_path / "destino")

    assert resultado.exitosa is False
    assert resultado.detalle == "clave incorrecta"
