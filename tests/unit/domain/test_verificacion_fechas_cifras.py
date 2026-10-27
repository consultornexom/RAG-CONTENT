from __future__ import annotations

from domain.documents.verificacion_fechas_cifras import (
    TipoHallazgoVerificacion,
    detectar_fechas_y_cifras,
)


def test_texto_sin_fechas_ni_cifras_no_produce_hallazgos() -> None:
    assert detectar_fechas_y_cifras("Este documento no contiene datos numericos.") == []


def test_detecta_fecha_formato_dd_mm_aaaa() -> None:
    hallazgos = detectar_fechas_y_cifras("La revision vence el 12/05/2026.")
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == TipoHallazgoVerificacion.FECHA
    assert hallazgos[0].texto == "12/05/2026"


def test_detecta_fecha_formato_iso() -> None:
    hallazgos = detectar_fechas_y_cifras("Fecha de emision: 2026-05-12.")
    assert len(hallazgos) == 1
    assert hallazgos[0].texto == "2026-05-12"


def test_detecta_fecha_en_espanol_con_mes_escrito() -> None:
    hallazgos = detectar_fechas_y_cifras("Emitido el 12 de mayo de 2026 en la ciudad de Mexico.")
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == TipoHallazgoVerificacion.FECHA
    assert hallazgos[0].texto.lower() == "12 de mayo de 2026"


def test_detecta_cifra_con_signo_de_moneda() -> None:
    hallazgos = detectar_fechas_y_cifras("El monto total es $1,234.56 pesos.")
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == TipoHallazgoVerificacion.CIFRA
    assert hallazgos[0].texto == "$1,234.56"


def test_detecta_cifra_con_porcentaje() -> None:
    hallazgos = detectar_fechas_y_cifras("La tasa aplicable es 45.5% sobre el saldo.")
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == TipoHallazgoVerificacion.CIFRA
    assert hallazgos[0].texto == "45.5%"


def test_hallazgos_quedan_ordenados_por_posicion() -> None:
    texto = "El 12/05/2026 se pago $1,000.00 y el 20/06/2026 se pago $2,000.00."
    hallazgos = detectar_fechas_y_cifras(texto)
    posiciones = [h.posicion for h in hallazgos]
    assert posiciones == sorted(posiciones)
    assert [h.texto for h in hallazgos] == ["12/05/2026", "$1,000.00", "20/06/2026", "$2,000.00"]


def test_posicion_reportada_coincide_con_el_indice_real_en_el_texto() -> None:
    texto = "Prefijo sin importancia. Vence 12/05/2026 aqui."
    hallazgo = detectar_fechas_y_cifras(texto)[0]
    assert texto[hallazgo.posicion : hallazgo.posicion + len(hallazgo.texto)] == hallazgo.texto


# -- Nivel 2: validacion de calendario (2026-08-01) ---------------------


def test_fecha_valida_no_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("La revision vence el 12/05/2026.")[0]
    assert hallazgo.advertencia is None


def test_cifra_nunca_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("El monto total es $1,234.56 pesos.")[0]
    assert hallazgo.tipo == TipoHallazgoVerificacion.CIFRA
    assert hallazgo.advertencia is None


def test_fecha_con_dia_fuera_de_rango_para_el_mes_tiene_advertencia() -> None:
    # Abril solo tiene 30 dias.
    hallazgo = detectar_fechas_y_cifras("La revision vence el 31/04/2026.")[0]
    assert hallazgo.advertencia is not None
    assert "dia" in hallazgo.advertencia


def test_fecha_con_mes_fuera_de_rango_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("La revision vence el 12/13/2026.")[0]
    assert hallazgo.advertencia is not None
    assert "mes" in hallazgo.advertencia


def test_29_de_febrero_en_ano_no_bisiesto_tiene_advertencia() -> None:
    # 2026 no es bisiesto (2024 y 2028 si).
    hallazgo = detectar_fechas_y_cifras("Firmado el 29/02/2026.")[0]
    assert hallazgo.advertencia is not None


def test_29_de_febrero_en_ano_bisiesto_no_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("Firmado el 29/02/2024.")[0]
    assert hallazgo.advertencia is None


def test_fecha_iso_invalida_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("Fecha de emision: 2026-02-30.")[0]
    assert hallazgo.advertencia is not None


def test_fecha_iso_valida_no_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("Fecha de emision: 2026-05-12.")[0]
    assert hallazgo.advertencia is None


def test_fecha_en_espanol_invalida_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("Emitido el 31 de abril de 2026 en la ciudad de Mexico.")[0]
    assert hallazgo.advertencia is not None


def test_fecha_en_espanol_valida_no_tiene_advertencia() -> None:
    hallazgo = detectar_fechas_y_cifras("Emitido el 12 de mayo de 2026 en la ciudad de Mexico.")[0]
    assert hallazgo.advertencia is None


def test_fecha_numerica_con_anio_de_dos_digitos_se_valida_como_20xx() -> None:
    # '30/02/26' -> 30 de febrero de 2026: invalido (febrero no llega a 30
    # en ningun anio). Confirma que el anio de 2 digitos se expande antes
    # de validar, no se ignora.
    hallazgo = detectar_fechas_y_cifras("Vigente desde 30/02/26.")[0]
    assert hallazgo.advertencia is not None
