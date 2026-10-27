from __future__ import annotations

from datetime import date

import pytest

from domain.validity.entities import Fuente, Vigencia, vigencia_desconocida

_DOC_ID = "DOC-0001"


def _fuente(**overrides) -> Fuente:
    datos = {
        "documento_id": _DOC_ID,
        "sistema_origen": "portal de normatividad interna",
        "autoridad": "Direccion Juridica",
        "evidencia_consulta": "Consultado en https://intranet/normativa el 2026-07-28",
    }
    datos.update(overrides)
    return Fuente(**datos)


def _vigencia(**overrides) -> Vigencia:
    datos = {"documento_id": _DOC_ID}
    datos.update(overrides)
    return Vigencia(**datos)


def test_fuente_rechaza_sistema_origen_vacio() -> None:
    with pytest.raises(ValueError):
        _fuente(sistema_origen="   ")


def test_fuente_rechaza_autoridad_vacia() -> None:
    with pytest.raises(ValueError):
        _fuente(autoridad="")


def test_fuente_rechaza_evidencia_consulta_vacia() -> None:
    with pytest.raises(ValueError):
        _fuente(evidencia_consulta="  ")


def test_fuente_actualizar_reemplaza_los_tres_campos() -> None:
    fuente = _fuente()
    actualizada = fuente.actualizar("otro sistema", "otra autoridad", "otra evidencia")
    assert actualizada.sistema_origen == "otro sistema"
    assert actualizada.autoridad == "otra autoridad"
    assert actualizada.evidencia_consulta == "otra evidencia"
    assert actualizada.documento_id == fuente.documento_id


def test_vigencia_nace_incompleta_por_defecto() -> None:
    vigencia = _vigencia()
    assert vigencia.esta_completa() is False


def test_vigencia_desconocida_cuando_no_existe_registro() -> None:
    assert vigencia_desconocida(None) is True


def test_vigencia_desconocida_cuando_esta_incompleta() -> None:
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1))  # sin autoridad ni fecha de fin
    assert vigencia_desconocida(vigencia) is True


def test_vigencia_conocida_con_fecha_de_vencimiento() -> None:
    vigencia = _vigencia(
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2027, 1, 1),
        autoridad="Direccion Juridica",
    )
    assert vigencia.esta_completa() is True
    assert vigencia_desconocida(vigencia) is False


def test_vigencia_conocida_sin_vencimiento_si_se_marca_explicito() -> None:
    vigencia = _vigencia(
        vigente_desde=date(2026, 1, 1),
        sin_vencimiento=True,
        autoridad="Direccion Juridica",
    )
    assert vigencia.esta_completa() is True
    assert vigencia_desconocida(vigencia) is False


def test_vigencia_incompleta_sin_vencimiento_pero_sin_marcar_el_flag() -> None:
    # vigente_hasta=None y sin_vencimiento=False (default) -- no se sabe
    # si es indefinida o si simplemente no se investigo: cuenta como
    # desconocida, a proposito (ver docstring de Vigencia.vigente_hasta).
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1), autoridad="Direccion Juridica")
    assert vigencia_desconocida(vigencia) is True


def test_vigencia_incompleta_sin_autoridad() -> None:
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1), vigente_hasta=date(2027, 1, 1))
    assert vigencia_desconocida(vigencia) is True


def test_esta_vigente_en_dentro_de_la_ventana() -> None:
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1), vigente_hasta=date(2026, 12, 31))
    assert vigencia.esta_vigente_en(date(2026, 6, 15)) is True


def test_esta_vigente_en_antes_de_vigente_desde() -> None:
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1), vigente_hasta=date(2026, 12, 31))
    assert vigencia.esta_vigente_en(date(2025, 12, 31)) is False


def test_esta_vigente_en_despues_de_vigente_hasta() -> None:
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1), vigente_hasta=date(2026, 12, 31))
    assert vigencia.esta_vigente_en(date(2027, 1, 1)) is False


def test_esta_vigente_en_con_sin_vencimiento_nunca_expira() -> None:
    vigencia = _vigencia(vigente_desde=date(2026, 1, 1), sin_vencimiento=True)
    assert vigencia.esta_vigente_en(date(2099, 1, 1)) is True


def test_vigencia_actualizar_reemplaza_todos_los_campos() -> None:
    vigencia = _vigencia()
    actualizada = vigencia.actualizar(
        fecha_emision=date(2025, 12, 1),
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 12, 31),
        sin_vencimiento=False,
        autoridad="Direccion Juridica",
        sustituye_a="DOC-0000",
    )
    assert actualizada.fecha_emision == date(2025, 12, 1)
    assert actualizada.vigente_desde == date(2026, 1, 1)
    assert actualizada.vigente_hasta == date(2026, 12, 31)
    assert actualizada.autoridad == "Direccion Juridica"
    assert actualizada.sustituye_a == "DOC-0000"
