"""Entidades del contexto Seguridad (Fase 10): value objects puros, sin
metodos de negocio -- las pruebas se limitan a construccion valida y a
que `fecha` se auto-complete en ISO 8601 cuando no se especifica (mismo
criterio de prueba minimo que `domain.reports.entities`)."""
from __future__ import annotations

from datetime import datetime

from domain.security.entities import RespaldoProyecto, RestauracionRespaldo
from domain.security.exceptions import ClaveDeRespaldoNoEncontradaError


def test_respaldo_proyecto_autocompleta_fecha_iso() -> None:
    respaldo = RespaldoProyecto(
        proyecto_id="PROY-0001",
        ruta_archivo="/tmp/respaldo.zip.enc",
        hash_sha256="a" * 64,
        tamano_bytes=1024,
    )

    assert datetime.fromisoformat(respaldo.fecha) is not None


def test_restauracion_respaldo_exitosa_por_defecto_sin_detalle() -> None:
    restauracion = RestauracionRespaldo(
        ruta_archivo="/tmp/respaldo.zip.enc",
        ruta_destino="/tmp/destino",
        exitosa=True,
    )

    assert restauracion.detalle == ""
    assert datetime.fromisoformat(restauracion.fecha) is not None


def test_restauracion_respaldo_puede_marcarse_no_exitosa_con_detalle() -> None:
    restauracion = RestauracionRespaldo(
        ruta_archivo="/tmp/respaldo.zip.enc",
        ruta_destino="/tmp/destino",
        exitosa=False,
        detalle="clave incorrecta",
    )

    assert restauracion.exitosa is False
    assert restauracion.detalle == "clave incorrecta"


def test_clave_de_respaldo_no_encontrada_incluye_el_proyecto_id() -> None:
    error = ClaveDeRespaldoNoEncontradaError("PROY-0001")

    assert "PROY-0001" in str(error)
    assert error.proyecto_id == "PROY-0001"
